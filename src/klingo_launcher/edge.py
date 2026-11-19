"""Abre o Edge *real* (perfil próprio) e expõe a porta CDP para o Playwright se conectar.

O Edge não é filho do Playwright: quando o exe termina, o navegador continua aberto
no painel, sem a faixa "controlado por software de teste".
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
import winreg
from pathlib import Path

import psutil

from .log import log

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


class EdgeErro(Exception):
    pass


def localizar(caminho_config: str = "") -> Path:
    candidatos: list[Path] = []
    if caminho_config:
        candidatos.append(Path(caminho_config))

    for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(
                raiz, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
            ) as chave:
                candidatos.append(Path(winreg.QueryValue(chave, None)))
        except OSError:
            pass

    for var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
        base = os.environ.get(var)
        if base:
            candidatos.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for c in candidatos:
        if c.is_file():
            return c
    raise EdgeErro("Microsoft Edge não encontrado. Informe [edge] caminho no config.toml")


def processos_do_perfil(perfil: Path) -> list[psutil.Process]:
    alvo = str(perfil).lower()
    achados = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower() != "msedge.exe":
                continue
            cmd = " ".join(p.info["cmdline"] or []).lower()
            if alvo in cmd:
                achados.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return achados


def fechar_perfil(perfil: Path, espera_seg: int = 10) -> None:
    """Fecha um Edge que tenha sobrado do nosso perfil (ex.: exe rodado de novo)."""
    procs = processos_do_perfil(perfil)
    if not procs:
        return
    log.info("Fechando %d processo(s) do Edge do perfil anterior", len(procs))
    for p in procs:
        try:
            p.terminate()
        except psutil.NoSuchProcess:
            pass
    _, vivos = psutil.wait_procs(procs, timeout=espera_seg)
    for p in vivos:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass


def _marcar_saida_limpa(perfil: Path) -> None:
    """Evita o balão 'Restaurar páginas?' depois de um desligamento forçado."""
    prefs = perfil / "Default" / "Preferences"
    if not prefs.is_file():
        return
    try:
        dados = json.loads(prefs.read_text(encoding="utf-8"))
        perfil_cfg = dados.setdefault("profile", {})
        perfil_cfg["exit_type"] = "Normal"
        perfil_cfg["exited_cleanly"] = True
        prefs.write_text(json.dumps(dados), encoding="utf-8")
    except (OSError, ValueError) as e:
        log.warning("Não consegui ajustar Preferences do Edge: %s", e)


def abrir(exe: Path, perfil: Path, porta: int, url: str, kiosk: bool = True) -> None:
    perfil.mkdir(parents=True, exist_ok=True)
    _marcar_saida_limpa(perfil)

    args = [
        str(exe),
        f"--user-data-dir={perfil}",
        f"--remote-debugging-port={porta}",
        "--remote-allow-origins=http://127.0.0.1",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=msEdgeSidebarV2,msHubApps,Translate",
        "--autoplay-policy=no-user-gesture-required",  # deixa o painel tocar som / falar
        "--hide-crash-restore-bubble",
    ]
    if kiosk:
        args += ["--kiosk", url, "--edge-kiosk-type=fullscreen"]
    else:
        args.append(url)

    log.info("Abrindo Edge (kiosk=%s, porta CDP %d)", kiosk, porta)
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        # Sai do "job" do Agendador de Tarefas: o Edge não pode morrer junto com o exe.
        _popen(args, flags | CREATE_BREAKAWAY_FROM_JOB)
    except OSError:
        _popen(args, flags)  # job não permite sair; abre normalmente


def _popen(args: list[str], flags: int) -> None:
    subprocess.Popen(
        args,
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def esperar_cdp(porta: int, timeout_seg: int = 60) -> str:
    """Espera o Edge responder na porta CDP e devolve o endpoint para o Playwright."""
    endpoint = f"http://127.0.0.1:{porta}"
    limite = time.monotonic() + timeout_seg
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f"{endpoint}/json/version", timeout=2) as r:
                if r.status == 200:
                    return endpoint
        except OSError:
            pass
        time.sleep(0.5)
    raise EdgeErro(f"Edge não abriu a porta CDP {porta} em {timeout_seg}s")

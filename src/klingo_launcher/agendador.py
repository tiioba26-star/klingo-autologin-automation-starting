"""Cria/remove as tarefas no Agendador de Tarefas do Windows.

- "Klingo - Abrir":    no logon do usuário → executa o exe.
- "Klingo - Desligar": todo dia no horário do config → exe --desligar.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from .config import Config
from .log import log

TAREFA_ABRIR = "Klingo - Abrir"
TAREFA_DESLIGAR = "Klingo - Desligar"
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


class AgendadorErro(Exception):
    pass


def eh_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def usuario_atual() -> str:
    return f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"


def reabrir_como_admin(args: list[str]) -> None:
    """Relança este exe pedindo elevação (janela do UAC)."""
    params = " ".join(f'"{a}"' for a in args)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if r <= 32:
        raise AgendadorErro("Permissão de administrador negada")


def _xml(descricao: str, gatilho: str, usuario: str, exe: Path, argumentos: str, limite: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="{NS}">
  <RegistrationInfo><Description>{escape(descricao)}</Description></RegistrationInfo>
  <Triggers>{gatilho}</Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(usuario)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>false</StartWhenAvailable>
    <ExecutionTimeLimit>{limite}</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(exe))}</Command>
      <Arguments>{escape(argumentos)}</Arguments>
      <WorkingDirectory>{escape(str(exe.parent))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _registrar(nome: str, xml: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-16") as f:
        f.write(xml)
        caminho = f.name
    try:
        r = subprocess.run(
            ["schtasks", "/create", "/tn", nome, "/xml", caminho, "/f"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    finally:
        os.unlink(caminho)
    if r.returncode != 0:
        raise AgendadorErro(f"Falha ao criar '{nome}': {r.stderr.strip() or r.stdout.strip()}")
    log.info("Tarefa criada: %s", nome)


def _executar(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode != 0:
        log.warning("%s → %s", " ".join(cmd), (r.stderr or r.stdout).strip())


def instalar(cfg: Config, usuario: str) -> None:
    if not getattr(sys, "frozen", False):
        raise AgendadorErro("--instalar só funciona a partir do .exe gerado pelo build.ps1")
    exe = Path(sys.executable).resolve()

    _registrar(
        TAREFA_ABRIR,
        _xml(
            "Abre o painel de chamada / totem da Klingo ao entrar no Windows.",
            f"<LogonTrigger><Enabled>true</Enabled><UserId>{escape(usuario)}</UserId></LogonTrigger>",
            usuario, exe, "", "PT1H",
        ),
    )
    _registrar(
        TAREFA_DESLIGAR,
        _xml(
            f"Fecha os apps e desliga o PC às {cfg.desligamento.horario}.",
            "<CalendarTrigger>"
            f"<StartBoundary>2026-01-01T{cfg.desligamento.horario}:00</StartBoundary>"
            "<Enabled>true</Enabled>"
            "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
            "</CalendarTrigger>",
            usuario, exe, "--desligar", "PT30M",
        ),
    )

    # Tela nunca apaga e o PC nunca suspende (na tomada e na bateria).
    for opcao in ("monitor-timeout-ac", "monitor-timeout-dc", "standby-timeout-ac", "standby-timeout-dc"):
        _executar(["powercfg", "/change", opcao, "0"])
    log.info("Energia: monitor e suspensão desativados")


def desinstalar() -> None:
    for nome in (TAREFA_ABRIR, TAREFA_DESLIGAR):
        _executar(["schtasks", "/delete", "/tn", nome, "/f"])
        log.info("Tarefa removida: %s", nome)

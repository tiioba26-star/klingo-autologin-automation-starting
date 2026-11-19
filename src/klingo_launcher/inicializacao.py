"""--instalar / --desinstalar: atalho do exe na pasta Inicializar (shell:startup). Não precisa de admin.

O atalho (e não o exe) vai para o startup porque o config.toml precisa ficar ao lado do exe,
e o Windows tentaria "abrir" o .toml a cada logon se ele estivesse na pasta Inicializar.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .log import log

NOME_ATALHO = "Klingo Automação.lnk"


class InicializacaoErro(Exception):
    pass


def pasta_startup() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _exe() -> Path:
    if not getattr(sys, "frozen", False):
        raise InicializacaoErro("--instalar só funciona a partir do .exe gerado pelo build.ps1")
    return Path(sys.executable).resolve()


def instalar() -> Path:
    exe = _exe()
    atalho = pasta_startup() / NOME_ATALHO
    # WScript.Shell via PowerShell: cria o .lnk sem dependências extras.
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:K_ATALHO);"
        "$s.TargetPath = $env:K_EXE; $s.WorkingDirectory = $env:K_PASTA;"
        "$s.Description = 'Abre o painel/totem da Klingo e desliga no horário'; $s.Save()"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "K_ATALHO": str(atalho), "K_EXE": str(exe), "K_PASTA": str(exe.parent)},
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if r.returncode != 0 or not atalho.is_file():
        raise InicializacaoErro(f"Não consegui criar o atalho: {r.stderr.strip()}")
    log.info("Atalho criado: %s -> %s", atalho, exe)
    return atalho


def desinstalar() -> None:
    atalho = pasta_startup() / NOME_ATALHO
    atalho.unlink(missing_ok=True)
    log.info("Atalho removido: %s", atalho)

"""Log em arquivo ao lado do exe — é o que vamos olhar quando algo der errado num PC."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("klingo")


def configurar(pasta: Path) -> None:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    arquivo = RotatingFileHandler(
        pasta / "klingo.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    arquivo.setFormatter(fmt)
    log.addHandler(arquivo)

    # No exe sem console, sys.stderr é None.
    if sys.stderr is not None:
        tela = logging.StreamHandler()
        tela.setFormatter(fmt)
        log.addHandler(tela)

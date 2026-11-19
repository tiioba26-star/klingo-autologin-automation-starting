"""Desligamento diário: avisa, fecha os apps educadamente e só então desliga."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime

from .config import Config
from .janelas import (
    InstanciaUnica,
    fechar_janelas_abertas,
    listar_janelas,
    manter_ligado,
    perguntar_cancelar,
)
from .log import log


def vigiar(cfg: Config, id_pasta: str) -> None:
    """Fica rodando escondido até o horário e então desliga.

    Substitui a tarefa agendada: basta o atalho no shell:startup.
    """
    d = cfg.desligamento
    if not d.ativo:
        log.info("Desligamento automático desativado no config")
        return

    unica = InstanciaUnica(f"klingo-vigia-{id_pasta}")
    if unica.ja_rodando:
        log.info("Vigia do desligamento já está rodando")
        return

    hh, mm = map(int, d.horario.split(":"))
    alvo = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if datetime.now() >= alvo:
        log.info("PC ligado depois das %s: hoje não desligo automaticamente", d.horario)
        return

    manter_ligado()
    log.info("Aguardando até %s para desligar (tela e PC não vão dormir até lá)", d.horario)
    while (falta := (alvo - datetime.now()).total_seconds()) > 0:
        time.sleep(min(30, falta))  # em pedaços: acompanha ajustes de relógio
    executar(cfg)


def executar(cfg: Config, simular: bool = False) -> None:
    d = cfg.desligamento
    cancelou = perguntar_cancelar(
        f"Este computador será DESLIGADO em {d.aviso_seg} segundos "
        f"(desligamento automático das {d.horario}).\n\n"
        "Clique em OK para desligar agora ou em Cancelar para NÃO desligar hoje.",
        d.aviso_seg,
    )
    if cancelou:
        log.info("Desligamento cancelado pelo usuário")
        return

    if simular:
        titulos = [t for _, t in listar_janelas()]
        log.info("[SIMULAÇÃO] fecharia %d janela(s): %s", len(titulos), titulos)
        log.info("[SIMULAÇÃO] não desliguei. Comando seria: shutdown /s /t 0%s", " /f" if d.forcar else "")
        return

    # 1) Pede para cada app fechar (igual a clicar no X): o Edge e os outros salvam o estado.
    titulos = fechar_janelas_abertas()
    log.info("Pedido de fechamento enviado para %d janela(s): %s", len(titulos), titulos)

    # 2) Espera os apps fecharem sozinhos.
    limite = time.monotonic() + d.espera_fechar_apps_seg
    restantes = listar_janelas()
    while restantes and time.monotonic() < limite:
        time.sleep(1)
        restantes = listar_janelas()
    if restantes:
        log.warning("Ainda abertas após %ds: %s", d.espera_fechar_apps_seg, [t for _, t in restantes])

    # 3) Desliga. /t 0 sem /f deixaria o Windows travado na tela "apps impedindo o desligamento"
    #    se algum app tiver algo não salvo; por isso /f é o padrão (configurável).
    cmd = ["shutdown", "/s", "/t", "0"]
    if d.forcar:
        cmd.append("/f")
    log.info("Desligando: %s", " ".join(cmd))
    subprocess.run(cmd, check=False, creationflags=subprocess.CREATE_NO_WINDOW)

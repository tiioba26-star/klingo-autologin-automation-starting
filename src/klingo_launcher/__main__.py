"""Ponto de entrada do klingo-launcher.exe.

    klingo-launcher.exe                 abre o painel/totem (o que roda no logon)
    klingo-launcher.exe --instalar      cria as tarefas (logon + desligamento) — pede admin
    klingo-launcher.exe --desinstalar   remove as tarefas
    klingo-launcher.exe --desligar      fecha os apps e desliga (o que roda às 18h)
    klingo-launcher.exe --vozes         lista e testa as vozes pt-BR do Edge
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import traceback
from pathlib import Path

from . import __version__, agendador, config, desligar, fluxo, vozes
from .janelas import MB_ICONERROR, InstanciaUnica, mensagem
from .log import configurar as configurar_log
from .log import log


def _args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="klingo-launcher")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--instalar", action="store_true")
    g.add_argument("--desinstalar", action="store_true")
    g.add_argument("--desligar", action="store_true")
    g.add_argument("--vozes", action="store_true")
    p.add_argument("--simular", action="store_true", help="com --desligar: faz tudo menos desligar")
    p.add_argument("--config", type=Path, help="caminho do config.toml (padrão: ao lado do exe)")
    p.add_argument("--usuario", help=argparse.SUPPRESS)  # passado ao relançar como admin
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = _args(argv)
    pasta = a.config.resolve().parent if a.config else config.pasta_base()
    configurar_log(pasta)
    log.info("=== klingo-launcher %s %s ===", __version__, " ".join(sys.argv[1:]))

    try:
        if a.desinstalar:
            if not agendador.eh_admin():
                agendador.reabrir_como_admin(["--desinstalar"])
                return 0
            agendador.desinstalar()
            mensagem("Tarefas removidas.")
            return 0

        if a.vozes:
            # Não exige config preenchido: só precisa do Edge.
            try:
                c = config.carregar(a.config)
                porta, caminho = c.edge.porta_cdp, c.edge.caminho
            except config.ConfigErro:
                porta, caminho = 9222, ""
            vozes.executar(pasta, porta, caminho)
            return 0

        cfg = config.carregar(a.config)

        if a.instalar:
            if not agendador.eh_admin():
                # Guarda o usuário de quem clicou: o admin do UAC pode ser outra conta.
                agendador.reabrir_como_admin(["--instalar", "--usuario", agendador.usuario_atual()])
                return 0
            usuario = a.usuario or agendador.usuario_atual()
            agendador.instalar(cfg, usuario)
            mensagem(
                f"Instalado para o usuário {usuario}.\n\n"
                f"• Abre o {cfg.painel.modo} sozinho ao entrar no Windows\n"
                f"• Desliga o PC todo dia às {cfg.desligamento.horario}"
            )
            return 0

        if a.desligar:
            desligar.executar(cfg, simular=a.simular)
            return 0

        # Uma execução por pasta (cada pasta = um perfil).
        pasta_id = hashlib.sha1(str(cfg.pasta).lower().encode()).hexdigest()[:12]
        unica = InstanciaUnica(f"klingo-launcher-{pasta_id}")
        if unica.ja_rodando:
            log.info("Já existe uma execução em andamento; saindo")
            return 0
        try:
            fluxo.executar(cfg)
        finally:
            unica.liberar()
        return 0

    except Exception as e:  # noqa: BLE001 — último recurso: registrar e avisar na tela
        log.error("Falhou: %s\n%s", e, traceback.format_exc())
        mensagem(
            f"Não consegui concluir automaticamente:\n\n{e}\n\n"
            f"Detalhes em: {pasta / 'klingo.log'}",
            icone=MB_ICONERROR,
            segundos=0 if a.instalar or a.desinstalar else 300,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

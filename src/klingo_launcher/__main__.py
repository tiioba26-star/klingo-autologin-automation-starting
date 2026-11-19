"""Ponto de entrada do klingo-launcher.exe.

    klingo-launcher.exe                 abre o painel/totem e fica esperando para desligar no horário
    klingo-launcher.exe --instalar      cria o atalho em shell:startup (não precisa de admin)
    klingo-launcher.exe --desinstalar   remove o atalho
    klingo-launcher.exe --desligar      aviso → fecha os apps → desliga (agora)
    klingo-launcher.exe --vozes         lista e testa as vozes pt-BR do Edge
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import traceback
from pathlib import Path

from . import __version__, config, desligar, fluxo, inicializacao, vozes
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
    return p.parse_args(argv)


def _avisar_erro(e: Exception, pasta: Path, segundos: int) -> None:
    log.error("Falhou: %s\n%s", e, traceback.format_exc())
    mensagem(
        f"Não consegui concluir automaticamente:\n\n{e}\n\nDetalhes em: {pasta / 'klingo.log'}",
        icone=MB_ICONERROR,
        segundos=segundos,
    )


def main(argv: list[str] | None = None) -> int:
    a = _args(argv)
    pasta = a.config.resolve().parent if a.config else config.pasta_base()
    configurar_log(pasta)
    log.info("=== klingo-launcher %s %s ===", __version__, " ".join(sys.argv[1:]))

    try:
        if a.desinstalar:
            inicializacao.desinstalar()
            mensagem("Atalho removido da Inicialização do Windows.")
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
            atalho = inicializacao.instalar()
            desl = (f"• Desliga o PC todo dia às {cfg.desligamento.horario}"
                    if cfg.desligamento.ativo else "• Desligamento automático: desativado")
            mensagem(
                f"Pronto! Atalho criado em:\n{atalho}\n\n"
                f"• Ao entrar no Windows, abre o {cfg.painel.modo} ({cfg.painel.recepcao})\n{desl}\n\n"
                "Não mova esta pasta de lugar (o atalho aponta para ela)."
            )
            return 0

        if a.desligar:
            desligar.executar(cfg, simular=a.simular)
            return 0
    except Exception as e:  # noqa: BLE001 — último recurso: registrar e avisar na tela
        _avisar_erro(e, pasta, segundos=0)
        return 1

    # ---- Execução normal (atalho do startup) ----------------------------------
    pasta_id = hashlib.sha1(str(cfg.pasta).lower().encode()).hexdigest()[:12]
    codigo = 0

    unica = InstanciaUnica(f"klingo-launcher-{pasta_id}")  # uma abertura por vez nesta pasta
    if unica.ja_rodando:
        log.info("Já existe uma abertura em andamento; saindo")
        return 0
    try:
        fluxo.executar(cfg)
    except Exception as e:  # noqa: BLE001
        _avisar_erro(e, pasta, segundos=300)
        codigo = 1
    finally:
        unica.liberar()

    # Mesmo se o painel falhou, o PC ainda precisa desligar no horário.
    try:
        desligar.vigiar(cfg, pasta_id)
    except Exception as e:  # noqa: BLE001
        _avisar_erro(e, pasta, segundos=300)
        codigo = 1
    return codigo


if __name__ == "__main__":
    sys.exit(main())

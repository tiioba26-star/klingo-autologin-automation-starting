"""Descobre o link direto de cada perfil (login → Localização → link) e grava links.json na raiz.

O build copia esse links.json para cada máquina: assim nenhuma precisa logar no primeiro boot.
Rode de novo se a Klingo trocar os links.   Uso:  python ferramentas/descobrir_links.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from klingo_launcher import config, edge, fluxo  # noqa: E402
from klingo_launcher.log import configurar  # noqa: E402

TRABALHO = RAIZ / "build" / "descobrir"
PORTA = 9230


def _config_do_perfil(modelo: Path, cred: dict) -> config.Config:
    texto = modelo.read_text(encoding="utf-8")
    for chave in ("url", "usuario", "senha"):
        texto = re.sub(rf'^{chave} = "PREENCHER"', lambda _m, c=chave: f"{c} = {json.dumps(cred[c], ensure_ascii=False)}",
                       texto, count=1, flags=re.M)
    destino = TRABALHO / modelo.name.removesuffix(".toml.exemplo") / "config.toml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return config.carregar(destino)


def main() -> int:
    TRABALHO.mkdir(parents=True, exist_ok=True)
    configurar(TRABALHO)
    cred = tomllib.loads((RAIZ / "credenciais.toml").read_text(encoding="utf-8-sig"))["klingo"]
    saida = RAIZ / "links.json"
    links = json.loads(saida.read_text(encoding="utf-8")) if saida.is_file() else {}

    perfil_edge = TRABALHO / "perfil-edge"
    edge.fechar_perfil(perfil_edge)
    edge.abrir(edge.localizar(), perfil_edge, PORTA, "about:blank", kiosk=False)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(edge.esperar_cdp(PORTA))
        page = browser.contexts[0].pages[0]
        for modelo in sorted((RAIZ / "perfis").glob("*.toml.exemplo")):
            cfg = _config_do_perfil(modelo, cred)
            page.set_default_timeout(cfg.tempos.timeout_passo_seg * 1000)
            link = fluxo.descobrir_link(page, cfg)
            page.goto(link, wait_until="domcontentloaded")
            if not fluxo._tela_certa(page, cfg):
                print(f"ERRO: link de {modelo.name} não abriu a tela esperada")
                return 1
            links[fluxo._chave(cfg)] = link
            print(f"  {modelo.name.removesuffix('.toml.exemplo'):12} {link}")
        browser.new_browser_cdp_session().send("Browser.close")

    saida.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Gravado em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

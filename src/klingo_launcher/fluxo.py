"""Fluxo principal: espera a rede → abre o Edge kiosk → login → unidade → voz → painel/totem."""

from __future__ import annotations

import random
import time
import unicodedata
import urllib.error
import urllib.request
from enum import Enum, auto

from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

from . import edge
from . import seletores as S
from .config import Config
from .log import log


class FluxoErro(Exception):
    pass


class Resultado(Enum):
    OK = auto()
    PAUSADO = auto()


# --------------------------------------------------------------------------- rede
def aguardar_rede(cfg: Config) -> None:
    atraso = cfg.tempos.atraso_inicial_seg
    log.info("Aguardando %ds antes de começar (internet subir)", atraso)
    time.sleep(atraso)

    limite = time.monotonic() + cfg.tempos.espera_internet_max_seg
    while True:
        try:
            urllib.request.urlopen(cfg.klingo.url, timeout=10).close()
            log.info("Klingo respondeu")
            return
        except urllib.error.HTTPError:
            # Qualquer resposta HTTP (até 401/403) prova que a rede está de pé.
            log.info("Klingo respondeu")
            return
        except OSError as e:
            if time.monotonic() > limite:
                raise FluxoErro(f"Sem acesso à Klingo depois de {cfg.tempos.espera_internet_max_seg}s: {e}")
            log.info("Klingo ainda inacessível (%s), tentando de novo em 10s", e)
            time.sleep(10)


# --------------------------------------------------------------------------- helpers
def _normalizar(texto: str) -> str:
    """'Antônio' == 'antonio': sem acento e minúsculo."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def _pausado(page: Page) -> bool:
    try:
        return page.get_by_text(S.TEXTO_PAUSADO).first.is_visible()
    except Exception:
        return False


def _esperar_um(page: Page, timeout_seg: int, **alvos) -> str:
    """Espera até um dos locators ficar visível ou a mensagem de pausado aparecer.

    Retorna o nome do alvo que apareceu, ou 'pausado'.
    """
    limite = time.monotonic() + timeout_seg
    while time.monotonic() < limite:
        if _pausado(page):
            return "pausado"
        for nome, loc in alvos.items():
            try:
                if loc.first.is_visible():
                    return nome
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise FluxoErro(f"Nenhum de {list(alvos)} apareceu em {timeout_seg}s (url: {page.url})")


def _pagina_principal(browser: Browser) -> Page:
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        for ctx in browser.contexts:
            for p in ctx.pages:
                if p.url.startswith("http"):
                    return p
        time.sleep(0.5)
    raise FluxoErro("Não encontrei a aba da Klingo no Edge")


# --------------------------------------------------------------------------- passos
def _login(page: Page, cfg: Config) -> None:
    log.info("Fazendo login como '%s'", cfg.klingo.usuario)
    page.locator(S.CAMPO_USUARIO).first.fill(cfg.klingo.usuario)
    page.locator(S.CAMPO_SENHA).first.fill(cfg.klingo.senha)
    page.get_by_role("button", name=S.BOTAO_ENTRAR).first.click()


def _escolher_unidade(page: Page, cfg: Config) -> None:
    if S.CAMPO_UNIDADE is None:
        raise FluxoErro("Seletor da unidade ainda não foi gravado (seletores.CAMPO_UNIDADE)")
    log.info("Selecionando unidade '%s'", cfg.painel.unidade)
    campo = page.locator(S.CAMPO_UNIDADE).first
    if campo.evaluate("e => e.tagName") == "SELECT":
        campo.select_option(label=cfg.painel.unidade)
    else:
        campo.click()
        page.get_by_text(cfg.painel.unidade, exact=True).first.click()


def _escolher_voz(page: Page, cfg: Config) -> None:
    if cfg.painel.modo != "painel" or not cfg.painel.voz:
        return
    if S.CAMPO_VOZ is None:
        log.warning("Seletor da voz não gravado; mantendo a voz padrão")
        return

    campo = page.locator(S.CAMPO_VOZ).first
    desejada = _normalizar(cfg.painel.voz)
    # Vozes online do Edge carregam de forma assíncrona; dá um tempo para aparecerem.
    opcoes: list[str] = []
    for _ in range(20):
        opcoes = [o.strip() for o in campo.locator("option").all_text_contents()]
        escolhida = next((o for o in opcoes if desejada in _normalizar(o)), None)
        if escolhida:
            campo.select_option(label=escolhida)
            log.info("Voz selecionada: %s", escolhida)
            return
        page.wait_for_timeout(500)
    log.warning("Voz '%s' não encontrada. Disponíveis: %s", cfg.painel.voz, opcoes)


def _abrir_tela_final(page: Page, cfg: Config) -> Page:
    nome = S.BOTAO_PAINEL if cfg.painel.modo == "painel" else S.BOTAO_TOTEM
    log.info("Abrindo %s", cfg.painel.modo)
    botao = page.get_by_role("button", name=nome).or_(page.get_by_role("link", name=nome)).first
    try:
        with page.context.expect_page(timeout=5000) as nova:
            botao.click()
        destino = nova.value
        log.info("%s abriu em nova aba", cfg.painel.modo)
    except PWTimeout:
        destino = page  # abriu na mesma aba
    destino.wait_for_load_state("domcontentloaded")
    destino.bring_to_front()
    return destino


def _tentativa(page: Page, cfg: Config) -> Resultado:
    t = cfg.tempos.timeout_passo_seg
    page.set_default_timeout(t * 1000)

    alvo_unidade = page.locator(S.CAMPO_UNIDADE) if S.CAMPO_UNIDADE else page.locator("#__nada__")
    etapa = _esperar_um(page, t, login=page.locator(S.CAMPO_SENHA), unidade=alvo_unidade)
    if etapa == "pausado":
        return Resultado.PAUSADO
    if etapa == "login":
        _login(page, cfg)
        etapa = _esperar_um(page, t, unidade=alvo_unidade)
        if etapa == "pausado":
            return Resultado.PAUSADO
    else:
        log.info("Sessão já estava logada")

    _escolher_unidade(page, cfg)
    _escolher_voz(page, cfg)
    if _pausado(page):
        return Resultado.PAUSADO

    final = _abrir_tela_final(page, cfg)
    final.wait_for_timeout(3000)
    if _pausado(final):
        return Resultado.PAUSADO
    log.info("Pronto: %s aberto em %s", cfg.painel.modo, final.url)
    return Resultado.OK


# --------------------------------------------------------------------------- principal
def executar(cfg: Config) -> None:
    inicio = time.monotonic()
    aguardar_rede(cfg)

    exe = edge.localizar(cfg.edge.caminho)
    edge.fechar_perfil(cfg.perfil_edge)
    edge.abrir(exe, cfg.perfil_edge, cfg.edge.porta_cdp, cfg.klingo.url, kiosk=True)
    endpoint = edge.esperar_cdp(cfg.edge.porta_cdp)

    with sync_playwright() as pw:
        # Não chamamos browser.close(): ao sair do 'with' só a conexão cai; o Edge fica aberto.
        browser = pw.chromium.connect_over_cdp(endpoint)
        page = _pagina_principal(browser)
        page.wait_for_load_state("domcontentloaded")

        for n in range(1, cfg.tempos.max_tentativas + 1):
            log.info("Tentativa %d/%d", n, cfg.tempos.max_tentativas)
            if _tentativa(page, cfg) is Resultado.OK:
                log.info("Concluído em %.0fs", time.monotonic() - inicio)
                return
            espera = cfg.tempos.espera_pausado_seg + random.randint(0, cfg.tempos.jitter_max_seg)
            log.warning("Klingo pausou por segundo acesso; outra máquina deve estar logando. Esperando %ds", espera)
            time.sleep(espera)
            page.goto(cfg.klingo.url, wait_until="domcontentloaded")

    raise FluxoErro(f"Não consegui abrir após {cfg.tempos.max_tentativas} tentativas (sempre pausado)")

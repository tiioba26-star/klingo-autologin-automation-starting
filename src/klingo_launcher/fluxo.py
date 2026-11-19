"""Fluxo principal.

Caminho normal (sem login):
    link direto salvo → painel: escolhe voz + "Iniciar o Painel com Chamada de Voz"
                      → totem: só confere que a tela abriu

Plano B (sem link salvo, ou o link não abriu a tela certa):
    login → [pausado? espera e clica Retomar] → Recepção → janela Localização
    → unidade + recepção do config → Atualizar → pega o link → salva → sai da conta → abre o link
"""

from __future__ import annotations

import json
import random
import time
import unicodedata
import urllib.error
import urllib.request

from playwright.sync_api import Browser, Locator, Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

from . import edge
from . import seletores as S
from .config import Config
from .log import log


class FluxoErro(Exception):
    pass


# --------------------------------------------------------------------------- utilidades
def normalizar(texto: str) -> str:
    """'RECEPÇÃO  Sus' == 'recepcao sus': sem acento, minúsculo, espaços simples."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def aguardar_rede(cfg: Config) -> None:
    atraso = cfg.tempos.atraso_inicial_seg
    log.info("Aguardando %ds antes de começar (internet subir)", atraso)
    time.sleep(atraso)

    limite = time.monotonic() + cfg.tempos.espera_internet_max_seg
    while True:
        try:
            urllib.request.urlopen(cfg.klingo.url, timeout=10).close()
            break
        except urllib.error.HTTPError:
            break  # qualquer resposta HTTP prova que a rede está de pé
        except OSError as e:
            if time.monotonic() > limite:
                raise FluxoErro(
                    f"Sem acesso à Klingo depois de {cfg.tempos.espera_internet_max_seg}s: {e}"
                ) from e
            log.info("Klingo ainda inacessível (%s), tentando de novo em 10s", e)
            time.sleep(10)
    log.info("Klingo respondeu")


def _chave(cfg: Config) -> str:
    p = cfg.painel
    partes = [p.modo, normalizar(p.unidade), normalizar(p.recepcao)]
    if p.modo == "totem":
        partes.append(normalizar(p.totem_botao))
    return "|".join(partes)


def _link_salvo(cfg: Config) -> str | None:
    if cfg.painel.link:
        return cfg.painel.link
    try:
        return json.loads(cfg.arquivo_links.read_text(encoding="utf-8")).get(_chave(cfg))
    except (OSError, ValueError):
        return None


def _salvar_link(cfg: Config, link: str) -> None:
    try:
        dados = json.loads(cfg.arquivo_links.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    dados[_chave(cfg)] = link
    cfg.arquivo_links.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Link guardado em %s", cfg.arquivo_links.name)


def _selecionar_por_texto(select: Locator, desejado: str, timeout_seg: int = 15) -> str:
    """Seleciona a opção cujo texto bate (sem acento/maiúscula). Espera as opções carregarem."""
    alvo = normalizar(desejado)
    opcoes: list[str] = []
    limite = time.monotonic() + timeout_seg
    while time.monotonic() < limite:
        opcoes = [o.strip() for o in select.locator("option").all_text_contents()]
        exata = next((o for o in opcoes if normalizar(o) == alvo), None)
        parecida = exata or next((o for o in opcoes if alvo in normalizar(o)), None)
        if parecida:
            select.select_option(label=parecida)
            return parecida
        time.sleep(0.5)
    raise FluxoErro(f"Opção '{desejado}' não encontrada. Opções disponíveis: {opcoes}")


def _pagina_principal(browser: Browser) -> Page:
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        for ctx in browser.contexts:
            for p in ctx.pages:
                if p.url.startswith("http"):
                    return p
        time.sleep(0.5)
    raise FluxoErro("Não encontrei a aba da Klingo no Edge")


# --------------------------------------------------------------------------- tela final
def _tela_certa(page: Page, cfg: Config) -> bool:
    """Confere se a página atual é o painel/totem da recepção configurada."""
    alvo = S.BOTAO_INICIAR_PAINEL if cfg.painel.modo == "painel" else S.TOTEM_PRONTO
    try:
        page.get_by_role("button", name=alvo).first.wait_for(
            state="visible", timeout=cfg.tempos.timeout_passo_seg * 1000
        )
    except PWTimeout:
        log.warning("A tela do %s não apareceu em %s", cfg.painel.modo, page.url)
        return False
    if normalizar(cfg.painel.recepcao) not in normalizar(page.locator("body").inner_text()):
        log.warning("A tela abriu, mas não é da recepção '%s'", cfg.painel.recepcao)
        return False
    return True


def _iniciar_painel(page: Page, cfg: Config) -> None:
    if cfg.painel.voz:
        # O <select> de voz é o que lista vozes "Microsoft ..."; as online chegam com atraso.
        select = page.locator("select").filter(has=page.locator("option", has_text="Microsoft")).first
        try:
            select.wait_for(state="visible", timeout=15000)
            escolhida = _selecionar_por_texto(select, cfg.painel.voz)
            log.info("Voz selecionada: %s", escolhida)
        except (PWTimeout, FluxoErro) as e:
            log.warning("Não consegui escolher a voz '%s' (%s); seguindo com a padrão", cfg.painel.voz, e)
    page.get_by_role("button", name=S.BOTAO_INICIAR_PAINEL).first.click()
    page.wait_for_timeout(2000)
    log.info("Painel iniciado com chamada de voz")


# --------------------------------------------------------------------------- plano B: login
class _Pausas:
    """Trata 'Pausado devido a segundo acesso' sempre que aparecer, em qualquer passo."""

    def __init__(self, page: Page, cfg: Config):
        self.page, self.cfg, self.vezes = page, cfg, 0

    def __call__(self, modal: Locator) -> None:
        self.vezes += 1
        if self.vezes > self.cfg.tempos.max_tentativas:
            raise FluxoErro(f"Pausado por segundo acesso {self.vezes - 1} vezes seguidas; desisti")
        espera = self.cfg.tempos.espera_pausado_seg + random.randint(0, self.cfg.tempos.jitter_max_seg)
        log.warning(
            "Pausado devido a segundo acesso (%dª vez). Outra máquina deve estar abrindo; espero %ds e retomo",
            self.vezes, espera,
        )
        self.page.wait_for_timeout(espera * 1000)
        # O botão fica "Retomar em N segs..." e só depois vira "Retomar".
        modal.get_by_role("button", name=S.BOTAO_RETOMAR).click(timeout=120_000)
        log.info("Retomado")


def _abrir_localizacao(page: Page) -> Locator:
    page.locator(S.LINK_LOCALIZACAO).filter(visible=True).first.click()
    modal = page.locator(S.MODAL_LOCALIZACAO)
    modal.wait_for(state="visible")
    return modal


def _sair_da_conta(page: Page) -> None:
    try:
        menu = page.locator(S.MENU_USUARIO)
        if not menu.is_visible():
            page.locator(S.MENU_RECOLHIDO).filter(visible=True).first.click(timeout=5000)
        menu.click(timeout=5000)
        page.locator(".dropdown-item", has_text=S.ITEM_SAIR).first.click(timeout=5000)
        page.wait_for_timeout(1500)
        log.info("Saí da conta (libera o usuário para as outras máquinas)")
    except PWTimeout:
        log.warning("Não consegui sair da conta; seguindo mesmo assim")


def descobrir_link(page: Page, cfg: Config) -> str:
    base = cfg.klingo.url.split("#")[0].rstrip("/") + "/"
    pausas = _Pausas(page, cfg)
    page.add_locator_handler(page.locator(S.MODAL_PAUSA), pausas)
    try:
        page.goto(base + "#/", wait_until="domcontentloaded")
        senha = page.get_by_role("textbox", name=S.CAMPO_SENHA)
        try:
            senha.wait_for(state="visible", timeout=10000)
            log.info("Fazendo login como '%s'", cfg.klingo.usuario)
            page.get_by_role("textbox", name=S.CAMPO_USUARIO).fill(cfg.klingo.usuario)
            senha.fill(cfg.klingo.senha)
            page.get_by_role("button", name=S.BOTAO_ENTRAR).click()
            senha.wait_for(state="hidden")
        except PWTimeout:
            log.info("Sem tela de login: sessão já estava aberta")

        page.goto(base + S.ROTA_RECEPCAO, wait_until="domcontentloaded")
        modal = _abrir_localizacao(page)
        selects = modal.locator("select")
        u = _selecionar_por_texto(selects.nth(0), cfg.painel.unidade)
        selects.nth(1).wait_for(state="visible")
        r = _selecionar_por_texto(selects.nth(1), cfg.painel.recepcao)
        log.info("Localização: %s / %s", u, r)
        modal.get_by_role("button", name=S.BOTAO_ATUALIZAR).click()
        page.wait_for_timeout(2000)
        if not modal.is_visible():
            modal = _abrir_localizacao(page)

        nome = S.LINK_PAINEL if cfg.painel.modo == "painel" else cfg.painel.totem_botao
        link = modal.get_by_role("link", name=nome, exact=True).first.get_attribute("href")
        if not link or not link.startswith("http"):
            raise FluxoErro(f"Não achei o link '{nome}' na janela Localização")
        log.info("Link do %s: %s", cfg.painel.modo, link)

        modal.get_by_role("button", name="Fechar").click()
        _sair_da_conta(page)
        return link
    finally:
        page.remove_locator_handler(page.locator(S.MODAL_PAUSA))


# --------------------------------------------------------------------------- principal
def executar(cfg: Config) -> None:
    inicio = time.monotonic()
    aguardar_rede(cfg)

    link = _link_salvo(cfg)
    exe = edge.localizar(cfg.edge.caminho)
    edge.fechar_perfil(cfg.perfil_edge)
    edge.abrir(exe, cfg.perfil_edge, cfg.edge.porta_cdp, link or cfg.klingo.url, kiosk=True)
    endpoint = edge.esperar_cdp(cfg.edge.porta_cdp)

    with sync_playwright() as pw:
        # Nunca chamamos browser.close(): ao sair do 'with' só a conexão cai; o Edge fica aberto.
        browser = pw.chromium.connect_over_cdp(endpoint)
        page = _pagina_principal(browser)
        page.set_default_timeout(cfg.tempos.timeout_passo_seg * 1000)

        ok = False
        if link:
            log.info("Abrindo link direto: %s", link)
            ok = _tela_certa(page, cfg)

        tentativas = 3
        for n in range(1, tentativas + 1):
            if ok:
                break
            log.info("Buscando o link pela Klingo (tentativa %d/%d)", n, tentativas)
            try:
                link = descobrir_link(page, cfg)
            except (PWTimeout, FluxoErro) as e:
                log.warning("Falhou: %s", e)
                if n == tentativas:
                    raise
                continue
            page.goto(link, wait_until="domcontentloaded")
            ok = _tela_certa(page, cfg)
            if ok and not cfg.painel.link:
                _salvar_link(cfg, link)

        if not ok:
            raise FluxoErro(f"Não consegui abrir o {cfg.painel.modo} da recepção '{cfg.painel.recepcao}'")

        if cfg.painel.modo == "painel":
            _iniciar_painel(page, cfg)
        log.info("Pronto: %s aberto em %.0fs", cfg.painel.modo, time.monotonic() - inicio)

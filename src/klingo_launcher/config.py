"""Leitura do config.toml que fica na mesma pasta do exe."""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

NOME_ARQUIVO = "config.toml"
MODOS = ("painel", "totem")


def pasta_base() -> Path:
    """Pasta do exe (empacotado) ou pasta atual (rodando via python)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


class ConfigErro(Exception):
    pass


@dataclass(frozen=True)
class Klingo:
    url: str
    usuario: str
    senha: str


@dataclass(frozen=True)
class Painel:
    unidade: str
    modo: str
    voz: str


@dataclass(frozen=True)
class Tempos:
    atraso_inicial_seg: int
    espera_internet_max_seg: int
    espera_pausado_seg: int
    jitter_max_seg: int
    max_tentativas: int
    timeout_passo_seg: int


@dataclass(frozen=True)
class Edge:
    caminho: str
    porta_cdp: int


@dataclass(frozen=True)
class Desligamento:
    horario: str
    aviso_seg: int
    espera_fechar_apps_seg: int
    forcar: bool


@dataclass(frozen=True)
class Config:
    pasta: Path
    klingo: Klingo
    painel: Painel
    tempos: Tempos
    edge: Edge
    desligamento: Desligamento

    @property
    def perfil_edge(self) -> Path:
        return self.pasta / "perfil-edge"


def _secao(dados: dict, nome: str) -> dict:
    valor = dados.get(nome, {})
    if not isinstance(valor, dict):
        raise ConfigErro(f"[{nome}] precisa ser uma seção do TOML")
    return valor


def _obrigatorio(secao: dict, nome_secao: str, chave: str) -> str:
    valor = str(secao.get(chave, "")).strip()
    if not valor or valor.startswith("PREENCHER"):
        raise ConfigErro(f"Preencha '{chave}' na seção [{nome_secao}] do {NOME_ARQUIVO}")
    return valor


def carregar(caminho: Path | None = None) -> Config:
    caminho = caminho or pasta_base() / NOME_ARQUIVO
    if not caminho.is_file():
        raise ConfigErro(f"Arquivo não encontrado: {caminho}")
    try:
        dados = tomllib.loads(caminho.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigErro(f"Erro de sintaxe no {caminho.name}: {e}") from e

    k = _secao(dados, "klingo")
    p = _secao(dados, "painel")
    t = _secao(dados, "tempos")
    e = _secao(dados, "edge")
    d = _secao(dados, "desligamento")

    modo = str(p.get("modo", "painel")).strip().lower()
    if modo not in MODOS:
        raise ConfigErro(f"[painel] modo deve ser um de {MODOS}, veio '{modo}'")

    horario = str(d.get("horario", "18:00")).strip()
    hh, _, mm = horario.partition(":")
    if not (hh.isdigit() and mm.isdigit() and int(hh) < 24 and int(mm) < 60):
        raise ConfigErro(f"[desligamento] horario inválido: '{horario}' (use HH:MM)")

    return Config(
        pasta=caminho.resolve().parent,
        klingo=Klingo(
            url=_obrigatorio(k, "klingo", "url"),
            usuario=_obrigatorio(k, "klingo", "usuario"),
            senha=_obrigatorio(k, "klingo", "senha"),
        ),
        painel=Painel(
            unidade=_obrigatorio(p, "painel", "unidade"),
            modo=modo,
            voz=str(p.get("voz", "")).strip(),
        ),
        tempos=Tempos(
            atraso_inicial_seg=int(t.get("atraso_inicial_seg", 15)),
            espera_internet_max_seg=int(t.get("espera_internet_max_seg", 300)),
            espera_pausado_seg=int(t.get("espera_pausado_seg", 90)),
            jitter_max_seg=int(t.get("jitter_max_seg", 30)),
            max_tentativas=int(t.get("max_tentativas", 10)),
            timeout_passo_seg=int(t.get("timeout_passo_seg", 30)),
        ),
        edge=Edge(
            caminho=str(e.get("caminho", "")).strip(),
            porta_cdp=int(e.get("porta_cdp", 9222)),
        ),
        desligamento=Desligamento(
            horario=f"{int(hh):02d}:{int(mm):02d}",
            aviso_seg=int(d.get("aviso_seg", 60)),
            espera_fechar_apps_seg=int(d.get("espera_fechar_apps_seg", 30)),
            forcar=bool(d.get("forcar", True)),
        ),
    )

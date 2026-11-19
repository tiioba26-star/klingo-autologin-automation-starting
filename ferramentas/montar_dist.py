"""Monta maquinas/<máquina>/ com: klingo-launcher.exe + config.toml (preenchido) + links.json.

Uso (o build.ps1 chama isto):  python ferramentas/montar_dist.py
- Credenciais vêm de credenciais.toml (fora do git).
- links.json (da raiz, gerado por ferramentas/descobrir_links.py) evita login no primeiro boot.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXE = RAIZ / "build" / "pyinstaller" / "klingo-launcher.exe"
CREDENCIAIS = RAIZ / "credenciais.toml"
LINKS = RAIZ / "links.json"
SAIDA = RAIZ / "maquinas"

# pasta da máquina -> perfil (perfis/<perfil>.toml.exemplo)
MAQUINAS = {
    "particular-1": "particular",
    "particular-2": "particular",
    "consultorio": "consultorio",
    "farmacia": "farmacia",
    "totem": "totem",
}


def _toml_str(valor: str) -> str:
    # Escape JSON é compatível com string básica TOML (aspas, barra invertida, controle).
    return json.dumps(valor, ensure_ascii=False)


def main() -> int:
    if not EXE.is_file():
        print(f"ERRO: exe não encontrado em {EXE}. Rode o build.ps1.")
        return 1

    cred: dict = {}
    if CREDENCIAIS.is_file():
        cred = tomllib.loads(CREDENCIAIS.read_text(encoding="utf-8-sig")).get("klingo", {})
    else:
        print("AVISO: credenciais.toml não existe; os config.toml sairão com PREENCHER.")
    if not LINKS.is_file():
        print("AVISO: links.json não existe; cada máquina vai logar uma vez para descobrir o link.")

    for maquina, perfil in MAQUINAS.items():
        pasta = SAIDA / maquina
        pasta.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXE, pasta / EXE.name)

        texto = (RAIZ / "perfis" / f"{perfil}.toml.exemplo").read_text(encoding="utf-8")
        texto = texto.replace(f"# Perfil: {perfil}", f"# Máquina: {maquina} (perfil {perfil})", 1)
        for chave in ("url", "usuario", "senha"):
            if chave in cred:
                texto = re.sub(
                    rf'^{chave} = "PREENCHER"',
                    lambda _m, c=chave: f"{c} = {_toml_str(str(cred[c]))}",
                    texto,
                    count=1,
                    flags=re.M,
                )
        tomllib.loads(texto)  # garante que o arquivo gerado é TOML válido
        (pasta / "config.toml").write_text(texto, encoding="utf-8")
        if LINKS.is_file():
            shutil.copy2(LINKS, pasta / "links.json")
        print(f"  maquinas/{maquina:13} perfil {perfil}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Monta dist/<perfil>/ com o exe + config.toml já preenchido a partir de credenciais.toml.

Uso (o build.ps1 chama isto):  python ferramentas/montar_dist.py
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
SAIDA = RAIZ / "dist"


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

    for modelo in sorted((RAIZ / "perfis").glob("*.toml.exemplo")):
        perfil = modelo.name.removesuffix(".toml.exemplo")
        pasta = SAIDA / perfil
        pasta.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXE, pasta / EXE.name)

        texto = modelo.read_text(encoding="utf-8")
        for chave in ("url", "usuario", "senha"):
            if chave in cred:
                texto = re.sub(
                    rf'^{chave} = "PREENCHER"',
                    lambda _m, c=chave: f"{c} = {_toml_str(str(cred[c]))}",
                    texto,
                    count=1,
                    flags=re.M,
                )
        (pasta / "config.toml").write_text(texto, encoding="utf-8")
        tomllib.loads(texto)  # garante que o arquivo gerado é TOML válido
        print(f"  dist/{perfil}/  ->  {EXE.name} + config.toml")

    return 0


if __name__ == "__main__":
    sys.exit(main())

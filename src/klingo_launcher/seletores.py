"""Tudo que depende da tela da Klingo fica aqui.

Se a Klingo mudar o layout, só este arquivo precisa ser ajustado.
Valores marcados com GRAVAR são provisórios e serão substituídos pelos
seletores capturados com `playwright codegen`.
"""

import re

# --- Login ---------------------------------------------------------------
CAMPO_USUARIO = "input[type=email], input[name*=user i], input[name*=login i], input[type=text]"  # GRAVAR
CAMPO_SENHA = "input[type=password]"  # GRAVAR
BOTAO_ENTRAR = re.compile(r"^\s*(entrar|acessar|login)\s*$", re.I)  # GRAVAR (nome do botão)

# --- Sessão pausada por segundo acesso -------------------------------------
# Qualquer texto na página que bata com isto conta como "pausado".
TEXTO_PAUSADO = re.compile(r"pausad|segundo acesso|outro acesso|outra sess|já está conectad", re.I)  # GRAVAR

# --- Painel de chamada / totem ----------------------------------------------
CAMPO_UNIDADE = None  # GRAVAR: seletor do campo de unidade
CAMPO_VOZ = None  # GRAVAR: seletor do <select> de voz
BOTAO_PAINEL = re.compile(r"painel de chamada", re.I)  # GRAVAR
BOTAO_TOTEM = re.compile(r"totem", re.I)  # GRAVAR

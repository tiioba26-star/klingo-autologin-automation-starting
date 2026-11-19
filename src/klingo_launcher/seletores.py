"""Tudo que depende da tela da Klingo fica aqui.

Se a Klingo mudar o layout, só este arquivo precisa ser ajustado.
Capturado com `playwright codegen` + exploração em 19/11/2026.
"""

import re

# --- Login (https://ioba.klingo.app/#/) ---------------------------------------
CAMPO_USUARIO = "Usuário"  # textbox (nome acessível)
CAMPO_SENHA = "Senha"  # textbox
BOTAO_ENTRAR = "Entrar"

# --- "Pausado devido a segundo acesso" ---------------------------------------
# Janela que trava a tela; o botão mostra "Retomar em N segs..." e depois libera "Retomar".
MODAL_PAUSA = "#pausaLoginModal"
BOTAO_RETOMAR = re.compile(r"^\s*Retomar\s*$", re.I)

# --- Recepção → janela "Localização" -----------------------------------------
ROTA_RECEPCAO = "#/recepcao"
LINK_LOCALIZACAO = "#identificacao-local a"  # ícone/nome da unidade no topo à direita
MODAL_LOCALIZACAO = "#localGlobalModal"  # 1º select = Unidade, 2º = Recepção Associada
BOTAO_ATUALIZAR = "Atualizar"
LINK_PAINEL = "Abrir Painel de Chamada"
# O link do totem é o texto exato configurado em [painel] totem_botao.

# --- Sair da conta -----------------------------------------------------------
MENU_RECOLHIDO = "button.navbar-toggler"  # botão ☰ que aparece em janelas estreitas
MENU_USUARIO = "#navbarDropdown"
ITEM_SAIR = re.compile(r"^\s*Sair", re.I)

# --- Tela final ---------------------------------------------------------------
BOTAO_INICIAR_PAINEL = re.compile(r"Iniciar o Painel com Chamada de Voz", re.I)
TOTEM_PRONTO = re.compile(r"Check-In COM Agendamento", re.I)

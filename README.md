# Klingo Autologin — painéis de chamada e totem

Ao entrar no Windows, o `klingo-launcher.exe` espera a internet, abre o **Microsoft Edge em kiosk (tela cheia)** e abre o **painel de chamada** (com voz escolhida + "Chamada de Voz") ou o **totem**. Às **18h** o PC avisa, fecha os apps e desliga.

O Edge é obrigatório porque só ele tem as vozes naturais online (Francisca, Antônio, Thalita multilíngue).

## Como funciona

Os links do painel (`ioba.klingo.app/#/painel/...`) e do totem (`api.klingo.app/reg-checkin/...`) **abrem sem login**. Então:

1. **Caminho normal (~8 s):** abre o link guardado em `links.json`. No painel, escolhe a voz e clica em "Iniciar o Painel com Chamada de Voz".
2. **Plano B** (primeira vez, mudança no config ou link que parou de funcionar): faz login → Recepção → janela **Localização** → escolhe a unidade e a recepção do config → Atualizar → pega o link → guarda em `links.json` → **sai da conta** → abre o link.

## Perfis

| Pasta | Máquinas | Recepção | Tela | Voz |
|---|---|---|---|---|
| `particular` | 2 | RECEPÇÃO PARTICULAR | painel | Francisca |
| `consultorio` | 1 | RECEPCAO CONSULTORIO | painel | Antônio |
| `farmacia` | 1 | RECEPCAO FARMACIA | painel | Francisca |
| `totem` | 1 | RECEPÇÃO SUS | Totem para Check-In (Dt Nasc) | — |

Para mudar a recepção, o botão do totem ou a voz, edite `[painel]` no `config.toml` com o nome **exato** que aparece na Klingo (acento e maiúscula não importam). Na próxima execução o exe descobre o link novo sozinho.

Cada pasta tem só **`klingo-launcher.exe` + `config.toml`**. O exe é o mesmo nas 4; o que muda é o `config.toml`.

## Gerar as pastas (máquina do TI)

1. Copie `credenciais.toml.exemplo` para `credenciais.toml` e preencha url, usuário e senha. Esse arquivo **nunca** vai para o git.
2. Rode `powershell -ExecutionPolicy Bypass -File .\build.ps1`.
3. As 4 pastas prontas ficam em `dist\`.

## Instalar em cada PC

1. Copie a pasta do perfil para `C:\KlingoAutomacao\` (ou outro local fixo).
2. Opcional: rode `klingo-launcher.exe --vozes` para ouvir as vozes e ajustar `voz` no `config.toml`.
3. Rode `klingo-launcher.exe --instalar` e aceite o pedido de administrador. Isso:
   - cria a tarefa **Klingo - Abrir** (no logon do usuário);
   - cria a tarefa **Klingo - Desligar** (todo dia às 18:00);
   - impede que a tela apague e que o PC suspenda.
4. Saia do Windows e entre de novo para testar.

Para remover: `klingo-launcher.exe --desinstalar`.

## Comandos

| Comando | O que faz |
|---|---|
| `klingo-launcher.exe` | Abre o painel/totem (é o que roda no logon) |
| `--instalar` / `--desinstalar` | Cria/remove as tarefas agendadas |
| `--desligar` | Aviso de 60 s (com Cancelar) → fecha os apps → desliga |
| `--desligar --simular` | Mostra o que faria, sem fechar nada nem desligar |
| `--vozes` | Lista as vozes pt do Edge, fala uma frase de teste com cada uma e grava `vozes.txt` |

## "Pausado por segundo acesso"

Só acontece no plano B, porque o caminho normal não faz login. A Klingo só deixa uma sessão por usuário. Se aparecer **"Pausado devido a segundo acesso"**, o exe espera `espera_pausado_seg` mais um sorteio de 0 a `jitter_max_seg` segundos e clica em **Retomar**, até `max_tentativas` vezes. O sorteio evita que as máquinas fiquem tomando a sessão umas das outras.

## Problemas

- Tudo fica registrado em **`klingo.log`**, na pasta do exe.
- Para forçar a busca de um link novo, apague o `links.json`.
- Se falhar, aparece uma caixa de erro e o Edge continua aberto para alguém logar à mão.
- Se a Klingo mudar a tela, ajuste só [`src/klingo_launcher/seletores.py`](src/klingo_launcher/seletores.py) e rode o build de novo.
- Para sair do kiosk: `Alt+F4`.

## Desenvolvimento

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
$env:PYTHONPATH="src"; .\.venv\Scripts\python -m klingo_launcher --config caminho\config.toml
```

Para gravar uma nova versão do fluxo: `.\.venv\Scripts\playwright codegen --channel msedge <url>`. As gravações em `gravacoes/*.py` ficam fora do git porque contêm a senha digitada.

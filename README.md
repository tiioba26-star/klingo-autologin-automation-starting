# Klingo Autologin — painéis de chamada e totem

Ao entrar no Windows, o `klingo-launcher.exe` espera a internet, abre o **Microsoft Edge em kiosk (tela cheia)**, faz login na Klingo, escolhe a unidade e a voz e abre o **painel de chamada** ou o **totem**. Às **18h** o PC avisa, fecha os apps e desliga.

O Edge é obrigatório porque só ele tem as vozes naturais online (Francisca, Antônio, Thalita).

## Perfis

| Pasta | Máquinas | Unidade | Tela | Voz |
|---|---|---|---|---|
| `particular` | 2 | Recepção Particular | painel | Francisca |
| `consultorio` | 1 | Recepção Consultório | painel | Antônio |
| `farmacia` | 1 | Recepção Farmácia | painel | Francisca |
| `totem` | 1 | Recepção Consultório | totem | — |

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

A Klingo só deixa uma sessão abrindo por vez. Se aparecer essa mensagem, o exe espera `espera_pausado_seg` mais um sorteio de 0 a `jitter_max_seg` segundos, recarrega e tenta de novo, até `max_tentativas` vezes. O sorteio evita que as 5 máquinas tentem ao mesmo tempo.

## Problemas

- Tudo fica registrado em **`klingo.log`**, na pasta do exe.
- Se falhar, aparece uma caixa de erro e o Edge continua aberto para alguém logar à mão.
- Se a Klingo mudar a tela, ajuste só [`src/klingo_launcher/seletores.py`](src/klingo_launcher/seletores.py) e rode o build de novo.
- Para sair do kiosk: `Alt+F4`.

## Desenvolvimento

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
$env:PYTHONPATH="src"; .\.venv\Scripts\python -m klingo_launcher --config caminho\config.toml
```

Para gravar uma nova versão do fluxo: `.\.venv\Scripts\playwright codegen --channel msedge <url>`. As gravações em `gravacoes/*.py` ficam fora do git porque contêm a senha digitada.

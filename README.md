# Klingo Autologin — painéis de chamada e totem

Ao entrar no Windows, o `klingo-launcher.exe` espera a internet, abre o **Microsoft Edge em kiosk (tela cheia)** e abre o **painel de chamada** (com voz natural + "Chamada de Voz") ou o **totem**. Depois fica rodando escondido e, às **18h**, avisa, fecha os apps e desliga o PC.

Nada precisa ser instalado nos PCs: o exe já leva tudo, e o Edge já vem no Windows. O Edge é obrigatório porque só ele tem as vozes naturais online (Francisca, Antônio, Thalita multilíngue).

## Máquinas

Saem prontas em `maquinas\` (pasta fora do git porque contém a senha):

| Pasta | Recepção | Tela | Voz |
|---|---|---|---|
| `particular` (usada nos 2 PCs) | RECEPÇÃO PARTICULAR | painel | Thalita |
| `consultorio` | RECEPCAO CONSULTORIO | painel | Antônio |
| `farmacia` | RECEPCAO FARMACIA | painel | Francisca |
| `totem` | RECEPÇÃO SUS | Totem para Check-In (Dt Nasc) | — |

Cada pasta tem 3 arquivos: `klingo-launcher.exe`, `config.toml` e `links.json`.

## Instalar em cada PC

1. Copie a pasta da máquina para um lugar fixo, por exemplo `C:\Klingo\`. **Não** coloque a pasta dentro do `shell:startup`, senão o Windows tenta abrir o `config.toml` a cada logon.
2. Dê dois cliques em `klingo-launcher.exe --instalar`, ou crie um atalho do exe com `--instalar` no fim do destino e abra ele. Isso cria o atalho **"Klingo Automação"** em `shell:startup`, sem pedir administrador.
   - Ou faça à mão: botão direito no exe → Criar atalho → mova o atalho para `Win+R` → `shell:startup`.
3. Saia do Windows e entre de novo para testar.

Para remover: `klingo-launcher.exe --desinstalar`, ou apague o atalho em `shell:startup`.

## Como funciona

Os links do painel (`ioba.klingo.app/#/painel/...`) e do totem (`api.klingo.app/reg-checkin/...`) **abrem sem login**:

1. **Caminho normal (~9 s):** abre o link de `links.json`. No painel, escolhe a voz e clica em "Iniciar o Painel com Chamada de Voz".
2. **Plano B** (link ausente, config mudou ou o link parou de funcionar): faz login → Recepção → janela **Localização** → escolhe a unidade e a recepção do config → Atualizar → pega o link → guarda em `links.json` → **sai da conta** → abre o link.
3. **Desligamento:** o exe continua rodando escondido até `horario` (18:00). Enquanto isso, impede a tela de apagar e o PC de suspender. Na hora, mostra um aviso de 60 s com botão **Cancelar**, pede para cada app fechar (como clicar no X) e desliga. Se o PC for ligado depois das 18h, ele não desliga naquele dia.

### "Pausado devido a segundo acesso"

Só pode acontecer no plano B. A Klingo deixa uma sessão por usuário. Quando a mensagem aparece, o exe espera `espera_pausado_seg` mais um sorteio de 0 a `jitter_max_seg` segundos e clica em **Retomar**, até `max_tentativas` vezes.

## Mudar recepção, totem ou voz

Edite `[painel]` no `config.toml` usando o nome **exato** da Klingo (acento e maiúscula não importam). Na próxima execução o exe descobre o link novo sozinho. Para ver as vozes disponíveis: `klingo-launcher.exe --vozes`.

## Comandos

| Comando | O que faz |
|---|---|
| `klingo-launcher.exe` | Abre o painel/totem e espera o horário para desligar (é o que o atalho roda) |
| `--instalar` / `--desinstalar` | Cria/remove o atalho em `shell:startup` |
| `--desligar` | Desliga agora: aviso → fecha os apps → desliga |
| `--desligar --simular` | Mostra o que faria, sem fechar nada nem desligar |
| `--vozes` | Lista as vozes pt do Edge, fala uma frase com cada uma e grava `vozes.txt` |

## Problemas

- Tudo fica registrado em **`klingo.log`**, na pasta do exe.
- Se falhar, aparece uma caixa de erro e o Edge continua aberto para alguém fazer à mão.
- Para forçar a busca de um link novo, apague o `links.json`.
- Se a Klingo mudar a tela, ajuste só [`src/klingo_launcher/seletores.py`](src/klingo_launcher/seletores.py) e rode o build de novo.
- Para sair do kiosk: `Alt+F4`.

## Gerar as pastas (máquina do TI)

```powershell
copy credenciais.toml.exemplo credenciais.toml   # preencha url, usuario, senha (fica fora do git)
.\.venv\Scripts\python ferramentas\descobrir_links.py   # opcional: gera links.json (evita login no 1º boot)
powershell -ExecutionPolicy Bypass -File .\build.ps1     # gera maquinas\
```

Desenvolvimento: `$env:PYTHONPATH="src"; .\.venv\Scripts\python -m klingo_launcher --config caminho\config.toml`.
Para regravar o fluxo: `.\.venv\Scripts\playwright codegen --channel msedge https://ioba.klingo.app`. As gravações em `gravacoes/*.py` ficam fora do git porque contêm a senha digitada.

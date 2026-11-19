"""--vozes: lista as vozes pt-BR que o Edge enxerga neste PC e fala uma frase de teste com cada uma."""

from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import edge
from .log import log

FRASE = "Senha A zero doze, por favor, dirija-se ao guichê três."

PAGINA = """<!doctype html><meta charset="utf-8"><title>Teste de vozes</title>
<body style="font:20px sans-serif;padding:2em">
<button id="ok" style="font-size:24px">Testar vozes</button><pre id="saida"></pre>
<script>
window.vozesPt = () => speechSynthesis.getVoices()
  .filter(v => v.lang.toLowerCase().startsWith('pt'))
  .map(v => ({nome: v.name, lang: v.lang, online: !v.localService}));

window.falar = (nomes, frase) => new Promise(resolve => {
  const fila = [...nomes];
  const proxima = () => {
    const nome = fila.shift();
    if (!nome) return resolve();
    document.getElementById('saida').textContent = 'Falando: ' + nome;
    const u = new SpeechSynthesisUtterance(nome.split(' - ')[0].replace('Microsoft ', '') + '. ' + frase);
    u.voice = speechSynthesis.getVoices().find(v => v.name === nome);
    u.onend = u.onerror = () => setTimeout(proxima, 600);
    speechSynthesis.speak(u);
  };
  proxima();
});
document.getElementById('ok').onclick = () => { window.clicou = true; };
</script>"""


def executar(pasta: Path, porta: int, caminho_edge: str = "") -> Path:
    perfil = pasta / "perfil-edge"
    edge.fechar_perfil(perfil)
    edge.abrir(edge.localizar(caminho_edge), perfil, porta, "about:blank", kiosk=False)
    endpoint = edge.esperar_cdp(porta)

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(endpoint)
        page = browser.contexts[0].pages[0]
        page.set_content(PAGINA)

        # Vozes online chegam depois; espera a lista estabilizar.
        vozes, anterior = [], -1
        for _ in range(20):
            vozes = page.evaluate("vozesPt()")
            if vozes and len(vozes) == anterior:
                break
            anterior = len(vozes)
            page.wait_for_timeout(500)

        linhas = [f"{'ONLINE ' if v['online'] else 'LOCAL  '} {v['nome']}  ({v['lang']})" for v in vozes]
        log.info("Vozes pt encontradas:\n%s", "\n".join(linhas) or "(nenhuma)")
        arquivo = pasta / "vozes.txt"
        arquivo.write_text(
            "Copie o nome exato (depois de ONLINE/LOCAL) para 'voz' no config.toml.\n"
            "Também vale só um pedaço, ex.: voz = \"Antonio\".\n\n" + "\n".join(linhas),
            encoding="utf-8-sig",
        )

        # O clique real (via Playwright) conta como gesto do usuário, exigido para falar.
        page.click("#ok")
        page.evaluate("([n, f]) => falar(n, f)", [[v["nome"] for v in vozes], FRASE])

        browser.new_browser_cdp_session().send("Browser.close")

    subprocess.Popen(["notepad.exe", str(arquivo)])
    return arquivo

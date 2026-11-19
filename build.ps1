# Gera maquinas\<máquina>\ (exe + config.toml + links.json) para as 5 máquinas.
# Antes, uma vez: credenciais.toml preenchido e (opcional) python ferramentas\descobrir_links.py
# Uso:  powershell -ExecutionPolicy Bypass -File .\build.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
}
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm --clean --onefile --windowed `
    --name klingo-launcher `
    --paths src `
    --distpath build\pyinstaller `
    --workpath build\work `
    --specpath build `
    lancador.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

.\.venv\Scripts\python.exe ferramentas\montar_dist.py
if ($LASTEXITCODE -ne 0) { throw "Falha ao montar as pastas" }

Write-Host "`nPronto. Copie cada pasta de maquinas\ para o PC correspondente." -ForegroundColor Green

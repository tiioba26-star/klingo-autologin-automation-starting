# Gera dist\<perfil>\klingo-launcher.exe + config.toml para os 4 perfis.
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
if ($LASTEXITCODE -ne 0) { throw "Falha ao montar dist" }

Write-Host "`nPronto. Copie cada pasta de dist\ para o PC correspondente." -ForegroundColor Green

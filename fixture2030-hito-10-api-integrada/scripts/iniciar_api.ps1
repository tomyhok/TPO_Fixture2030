# =====================================================================
# Hito 10 - Iniciar la API REST integrada
# =====================================================================
# Crea el entorno virtual si no existe, instala dependencias y levanta
# uvicorn con el host y puerto del .env. Los logs se ven en consola y se
# guardan en logs\api.log (excluido del repositorio).
#
# Uso (desde fixture2030-hito-10-api-integrada\): .\scripts\iniciar_api.ps1
# Detener: Ctrl+C (no afecta a los contenedores ni a sus datos).
# =====================================================================
$ErrorActionPreference = "Stop"
$hito = Split-Path -Parent $PSScriptRoot
Set-Location $hito

if (-not (Test-Path ".env")) {
    Write-Host "Falta .env: copiar .env.example a .env y completar las contraseñas."
    exit 1
}
if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual con Python 3.12..."
    py -3.12 -m venv .venv
}
$py = ".venv\Scripts\python.exe"
& $py -m pip install -q -r requirements.txt

$apiHost = ((Select-String -Path .env -Pattern '^API_HOST=').Line -replace '^API_HOST=', '')
$apiPort = ((Select-String -Path .env -Pattern '^API_PORT=').Line -replace '^API_PORT=', '')
if (-not $apiHost) { $apiHost = "127.0.0.1" }
if (-not $apiPort) { $apiPort = "8000" }

New-Item -ItemType Directory -Force logs | Out-Null
Write-Host "API en http://${apiHost}:${apiPort}  -  Swagger UI: http://${apiHost}:${apiPort}/docs"
& $py -m uvicorn app.main:app --host $apiHost --port $apiPort --no-access-log 2>&1 | Tee-Object -FilePath logs\api.log -Append

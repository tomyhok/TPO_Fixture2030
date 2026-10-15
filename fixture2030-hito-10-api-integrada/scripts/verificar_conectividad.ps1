# =====================================================================
# Hito 10 - Verificar contenedores y conectividad de las seis fuentes
# Uso (desde fixture2030-hito-10-api-integrada\): .\scripts\verificar_conectividad.ps1
# =====================================================================
$hito = Split-Path -Parent $PSScriptRoot
$py = Join-Path $hito ".venv\Scripts\python.exe"

Write-Host "=== Contenedores ==="
docker ps --filter "name=fixture2030-" --format "table {{.Names}}\t{{.Status}}"
Write-Host ""
Write-Host "=== Conectividad desde la notebook (mismos adaptadores que la API) ==="
Push-Location $hito
& $py scripts\verificar_conectividad.py
$codigo = $LASTEXITCODE
Pop-Location
exit $codigo

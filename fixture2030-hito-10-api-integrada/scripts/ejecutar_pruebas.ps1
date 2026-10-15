# =====================================================================
# Hito 10 - Ejecutar las pruebas
# =====================================================================
#   .\scripts\ejecutar_pruebas.ps1          unitarias + integración
#   .\scripts\ejecutar_pruebas.ps1 unit     solo unitarias (sin bases)
# =====================================================================
param([string]$alcance = "todo")
$hito = Split-Path -Parent $PSScriptRoot
Set-Location $hito
$py = ".venv\Scripts\python.exe"

Write-Host "=== Pruebas unitarias ==="
& $py -m pytest tests/unit -q
if ($LASTEXITCODE -ne 0) { exit 1 }
if ($alcance -eq "unit") { exit 0 }

Write-Host ""
Write-Host "=== Conectividad ==="
& $py scripts\verificar_conectividad.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Hay fuentes sin conexión: levantar los contenedores y ejecutar scripts/preparar_datos.sh"
    exit 1
}

Write-Host ""
Write-Host "=== Pruebas de integración ==="
& $py -m pytest tests/integration -v
exit $LASTEXITCODE

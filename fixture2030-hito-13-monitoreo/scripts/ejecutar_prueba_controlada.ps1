# =====================================================================
# Hito 13 - Ejecutar prueba controlada y reversible (PowerShell)
# =====================================================================
$dirHito = Split-Path -Parent $PSScriptRoot
Set-Location $dirHito

python scripts/ejecutar_prueba_controlada.py --guardar @args
exit $LASTEXITCODE

# =====================================================================
# Hito 13 - Verificar targets y reglas en Prometheus (PowerShell)
# =====================================================================
$dirHito = Split-Path -Parent $PSScriptRoot
Set-Location $dirHito

python scripts/verificar_targets.py --guardar @args
exit $LASTEXITCODE

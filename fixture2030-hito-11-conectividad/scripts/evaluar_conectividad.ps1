# =====================================================================
# Hito 11 - Evaluación de conectividad desde PowerShell (sin Git Bash)
# =====================================================================
# Uso:
#   .\scripts\evaluar_conectividad.ps1                        modo completo
#   .\scripts\evaluar_conectividad.ps1 --modo tcp
#   .\scripts\evaluar_conectividad.ps1 --modo nativo --producto redis,iris
#   $env:MONGO_HOST = "mongodb"; .\scripts\evaluar_conectividad.ps1 --modo tcp --producto mongodb
# Los scripts de fallo controlado y escenarios necesitan bash (Git Bash).
# =====================================================================
$hito = Split-Path -Parent $PSScriptRoot
$raiz = Split-Path -Parent $hito
$candidatos = @(
    $env:PYTHON,
    (Join-Path $raiz "fixture2030-hito-10-api-integrada\.venv\Scripts\python.exe"),
    (Join-Path $hito ".venv\Scripts\python.exe")
)
$py = $candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $py) { $py = "python" }

& $py (Join-Path $PSScriptRoot "evaluar_conectividad.py") @args
exit $LASTEXITCODE

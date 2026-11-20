# =====================================================================
# Hito 13 - Iniciar el stack de monitoreo (PowerShell)
# =====================================================================
$ErrorActionPreference = "Stop"
$dirHito = Split-Path -Parent $PSScriptRoot
Set-Location $dirHito

if (-not (Test-Path ".env")) {
    # RNF6: la contraseña de Grafana no se versiona; se genera una aleatoria local.
    $chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    $pass = -join (1..20 | ForEach-Object { $chars | Get-Random })
    Set-Content -Path ".env" -Value "GRAFANA_ADMIN_PASSWORD=$pass" -Encoding ascii
    Write-Host "  -> Se creo .env con una contrasena aleatoria para Grafana (no se versiona)."
}

Write-Host "=== [1/3] Levantando stack de monitoreo (compose: dash) ==="
docker compose up -d

Write-Host "=== [2/3] Esperando disponibilidad de Prometheus (http://localhost:9090) ==="
for ($i = 1; $i -le 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:9090/-/ready" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            Write-Host "  -> Prometheus listo."
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

Write-Host "=== [3/3] Esperando disponibilidad de Grafana (http://localhost:3000) ==="
for ($i = 1; $i -le 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            Write-Host "  -> Grafana listo."
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

docker compose ps
Write-Host ""
Write-Host "Accesos:"
Write-Host "  - Prometheus:     http://localhost:9090/targets"
Write-Host "  - Reglas/Alertas: http://localhost:9090/alerts"
Write-Host "  - Grafana:        http://localhost:3000 (usuario admin; contrasena en .env -> GRAFANA_ADMIN_PASSWORD)"
Write-Host "  - API /metrics:   http://localhost:8000/metrics"

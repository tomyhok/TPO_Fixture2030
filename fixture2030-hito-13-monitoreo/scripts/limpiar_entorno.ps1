# =====================================================================
# Hito 13 - Limpiar entorno de monitoreo (PowerShell, no destructivo RNF11)
# =====================================================================
$ErrorActionPreference = "Stop"
$dirHito = Split-Path -Parent $PSScriptRoot
Set-Location $dirHito

Write-Host "Deteniendo contenedores de monitoreo (prometheus, grafana, node-exporter)..."
Write-Host "Nota (RNF11): No se eliminan volumenes de datos de las bases NoSQL."
docker compose down
Write-Host "Entorno de monitoreo detenido correctamente."

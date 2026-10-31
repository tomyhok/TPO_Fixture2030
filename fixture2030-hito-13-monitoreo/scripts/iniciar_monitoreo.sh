#!/usr/bin/env bash
# =====================================================================
# Hito 13 - Iniciar el stack de monitoreo (Prometheus + Grafana + Node Exporter)
# =====================================================================
set -euo pipefail

DIR_HITO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_HITO"

echo "=== [1/3] Levantando stack de monitoreo (compose: dash) ==="
docker compose up -d

echo "=== [2/3] Esperando disponibilidad de Prometheus (http://localhost:9090) ==="
for i in {1..20}; do
  if curl -fsS "http://localhost:9090/-/ready" >/dev/null 2>&1; then
    echo "  -> Prometheus listo."
    break
  fi
  sleep 1
done

echo "=== [3/3] Esperando disponibilidad de Grafana (http://localhost:3000) ==="
for i in {1..20}; do
  if curl -fsS "http://localhost:3000/api/health" >/dev/null 2>&1; then
    echo "  -> Grafana listo."
    break
  fi
  sleep 1
done

echo ""
echo "Servicios activos:"
docker compose ps
echo ""
echo "Accesos:"
echo "  - Prometheus:    http://localhost:9090/targets"
echo "  - Reglas/Alertas: http://localhost:9090/alerts"
echo "  - Grafana:       http://localhost:3000 (admin / fixture2030)"
echo "  - API /metrics:  http://localhost:8000/metrics"

#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Verificar contenedores y conectividad de las seis fuentes
# Uso (desde fixture2030-hito-10-api-integrada/): bash scripts/verificar_conectividad.sh
# =====================================================================
set -uo pipefail
HITO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HITO/.venv/Scripts/python"; [ -x "$PY" ] || PY="$HITO/.venv/bin/python"

echo "=== Contenedores ==="
docker ps --filter "name=fixture2030-" --format "table {{.Names}}\t{{.Status}}"
echo
echo "=== Conectividad desde la notebook (mismos adaptadores que la API) ==="
cd "$HITO" && "$PY" scripts/verificar_conectividad.py

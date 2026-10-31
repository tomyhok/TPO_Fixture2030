#!/usr/bin/env bash
# =====================================================================
# Hito 13 - Limpiar entorno de monitoreo (sin borrar volúmenes de bases)
# =====================================================================
set -euo pipefail

DIR_HITO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_HITO"

echo "Deteniendo contenedores de monitoreo (prometheus, grafana, node-exporter)..."
echo "Nota (RNF11): No se eliminan volúmenes de datos de las bases NoSQL."
docker compose down
echo "Entorno de monitoreo detenido correctamente."

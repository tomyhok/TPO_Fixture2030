#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f .influxdb3-token ]; then
    echo "Error: Token no encontrado."
    exit 1
fi
TOKEN=$(cat .influxdb3-token)

echo "=== Validación del Objetivo de Carga (RF13) ==="
echo "Contando el total de puntos persistidos en la tabla estadisticas_partido..."

QUERY="
SELECT COUNT(posesion_pct) AS total_puntos_cargados
FROM estadisticas_partido
"

docker compose exec -T influxdb influxdb3 query \
  --database fixture2030 \
  --token "$TOKEN" \
  --format table \
  "$QUERY"

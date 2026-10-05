#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f .influxdb3-token ]; then
    echo "Error: Token no encontrado."
    exit 1
fi
TOKEN=$(cat .influxdb3-token)

echo "=== Consultas Temporales Básicas (RF8) ==="

# La consulta filtra por dimensiones (partido y equipo)
# y limita los resultados para simular una ventana acotada (TOP/LIMIT).
QUERY="
SELECT time, equipo_id, posesion_pct, pases_completados, tiros, usuarios_activos
FROM estadisticas_partido
WHERE partido_id = 'M001' AND equipo_id = 'EQ001_1'
ORDER BY time ASC
LIMIT 10
"

echo "Consulta SQL:"
echo "$QUERY"

echo "Resultados:"
docker compose exec -T influxdb influxdb3 query \
  --database fixture2030 \
  --token "$TOKEN" \
  --format table \
  "$QUERY"

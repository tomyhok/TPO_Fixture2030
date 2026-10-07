#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f .influxdb3-token ]; then
    echo "Error: Token no encontrado."
    exit 1
fi
TOKEN=$(cat .influxdb3-token)

consultar() {
  echo "Consulta SQL:"
  echo "$1"
  echo "Resultados:"
  docker exec -i fixture2030-influxdb influxdb3 query \
    --database fixture2030 \
    --token "$TOKEN" \
    --format pretty \
    "$1"
  echo
}

echo "=== Validación de la carga (RF13) ==="

# 1) Total de puntos, partidos y series cargadas.
echo "--- 1) Totales ---"
consultar "
SELECT COUNT(*) AS total_puntos,
       COUNT(DISTINCT partido_id) AS partidos,
       COUNT(DISTINCT partido_id || '/' || equipo_id) AS series
FROM estadisticas_partido
"

# 2) Distribución: cada serie debería tener la misma cantidad de puntos
#    (generacion_puntos.py reparte total_puntos / 254 por serie).
echo "--- 2) Puntos por serie (mínimo y máximo) ---"
consultar "
SELECT MIN(puntos) AS min_por_serie, MAX(puntos) AS max_por_serie
FROM (
  SELECT partido_id, equipo_id, COUNT(*) AS puntos
  FROM estadisticas_partido
  GROUP BY partido_id, equipo_id
) t
"

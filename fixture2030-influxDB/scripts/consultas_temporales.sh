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

echo "=== Consultas Temporales (RF8) ==="

# El partido M001 arranca a las 2030-06-01T03:40:00Z (ver generacion_puntos.py).
# 1) Ventana temporal: primeros 10 minutos del partido para un equipo.
#    Se acota el rango de tiempo y las dimensiones (RNF8).
echo "--- 1) Ventana de 10 minutos de M001 / EQ001_1 (primeros 10 puntos) ---"
consultar "
SELECT time, equipo_id, posesion_pct, pases_completados, tiros, usuarios_activos
FROM estadisticas_partido
WHERE partido_id = 'M001' AND equipo_id = 'EQ001_1'
  AND time >= '2030-06-01T03:40:00Z' AND time < '2030-06-01T03:50:00Z'
ORDER BY time ASC
LIMIT 10
"

# 2) Comparación entre dimensiones: los dos equipos de M001 en la misma ventana.
echo "--- 2) Comparación de los dos equipos de M001 en la misma ventana ---"
consultar "
SELECT equipo_id,
       COUNT(*) AS puntos,
       MIN(time) AS desde,
       MAX(time) AS hasta,
       ROUND(AVG(posesion_pct), 2) AS posesion_promedio,
       MAX(pases_completados) AS pases_al_cierre_ventana
FROM estadisticas_partido
WHERE partido_id = 'M001'
  AND time >= '2030-06-01T03:40:00Z' AND time < '2030-06-01T03:50:00Z'
GROUP BY equipo_id
ORDER BY equipo_id
"

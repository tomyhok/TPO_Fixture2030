#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f .influxdb3-token ]; then
    echo "Error: Token no encontrado."
    exit 1
fi
TOKEN=$(cat .influxdb3-token)

echo "=== Consultas de Agregación y Ventanas Temporales (RF9) ==="
echo "Calculando métricas agregadas por equipo para el partido M001..."

# Agregaciones:
# AVG(posesion_pct) -> Tiene sentido promediar la posesión en el tiempo.
# MAX(pases_completados) -> Al ser un contador que suma, el MAX representa el total acumulado al final.
# SUM(tiros) -> En el modelo original cada tiro puede ser un evento, pero aquí acumulamos.
# MAX(usuarios_activos) -> Muestra el pico de audiencia del partido.
QUERY="
SELECT equipo_id,
       AVG(posesion_pct) AS posesion_promedio,
       MAX(pases_completados) AS total_pases,
       SUM(tiros) AS total_tiros_registrados,
       MAX(usuarios_activos) AS pico_usuarios
FROM estadisticas_partido
WHERE partido_id = 'M001'
GROUP BY equipo_id
ORDER BY equipo_id
"

echo "Consulta SQL:"
echo "$QUERY"

echo "Resultados:"
docker compose exec -T influxdb influxdb3 query \
  --database fixture2030 \
  --token "$TOKEN" \
  --format table \
  "$QUERY"

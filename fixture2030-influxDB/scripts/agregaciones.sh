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

echo "=== Agregaciones (RF9) ==="

# Función de agregación según la semántica de cada medida:
# AVG(posesion_pct)      -> es un valor de muestra (porcentaje), se promedia.
# MAX(pases_completados) -> contador acumulado: el máximo es el total al final.
# MAX(tiros)             -> también es contador acumulado (sumarlo daría cualquier cosa).
# MAX(usuarios_activos)  -> medida que sube y baja: interesa el pico de audiencia.

# 1) Resumen del partido M001 por equipo.
echo "--- 1) Resumen de M001 por equipo ---"
consultar "
SELECT equipo_id,
       ROUND(AVG(posesion_pct), 2) AS posesion_promedio,
       MAX(pases_completados) AS total_pases,
       MAX(tiros) AS total_tiros,
       MAX(usuarios_activos) AS pico_usuarios
FROM estadisticas_partido
WHERE partido_id = 'M001'
  AND time >= '2030-06-01T03:40:00Z' AND time < '2030-06-01T06:00:00Z'
GROUP BY equipo_id
ORDER BY equipo_id
"

# 2) Agregación temporal: pico de usuarios y posesión promedio por minuto
#    (es el mismo resumen que se usaría para el downsampling histórico).
echo "--- 2) M001 / EQ001_1 agregado por minuto (primeros 10 minutos) ---"
consultar "
SELECT date_bin(INTERVAL '1 minute', time) AS minuto,
       MAX(usuarios_activos) AS pico_usuarios,
       ROUND(AVG(posesion_pct), 2) AS posesion_promedio,
       MAX(tiros) AS tiros_acumulados
FROM estadisticas_partido
WHERE partido_id = 'M001' AND equipo_id = 'EQ001_1'
  AND time >= '2030-06-01T03:40:00Z' AND time < '2030-06-01T03:50:00Z'
GROUP BY minuto
ORDER BY minuto
"

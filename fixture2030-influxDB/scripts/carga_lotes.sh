#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f data_estadisticas.lp ]; then
    echo "No se encontró data_estadisticas.lp. Generando 1,000,000 puntos para la demostración (modifica el script para 10M+ si tu RAM lo permite)..."
    python3 scripts/generacion_puntos.py 1000000 data_estadisticas.lp
fi

if [ ! -f .influxdb3-token ]; then
    echo "Error: No se encontró .influxdb3-token. Ejecuta primero scripts/inicializacion.sh"
    exit 1
fi
TOKEN=$(cat .influxdb3-token)

echo "Copiando archivo al contenedor para evitar cuellos de botella en la red local de Docker..."
docker cp data_estadisticas.lp fixture2030-influxdb:/tmp/data_estadisticas.lp

echo "Iniciando carga masiva usando la API de InfluxDB 3 (Batching y GZIP activados)..."
# La CLI maneja internamente la fragmentación según bytes y concurrencia.
# Se usa precisión temporal de segundos (s) porque así se generó.
docker compose exec -T influxdb influxdb3 write \
  --database fixture2030 \
  --token "$TOKEN" \
  --precision s \
  --gzip \
  --max-concurrent-requests 8 \
  --file /tmp/data_estadisticas.lp

echo "Carga completada. Limpiando archivos temporales del contenedor..."
docker compose exec -T influxdb rm /tmp/data_estadisticas.lp

echo "Carga exitosa."

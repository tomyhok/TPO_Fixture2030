#!/bin/bash
set -e

# Cambiar al directorio raíz del proyecto (donde está el docker-compose.yml de influxDB o el global)
cd "$(dirname "$0")/.."

echo "=== Inicializando InfluxDB 3 Core ==="

# Generar token si no existe
if [ ! -f .influxdb3-token ]; then
  echo "Creando token administrador..."
  # Se ejecuta el comando dentro del contenedor y se extrae el token
  TOKEN=$(docker compose exec -T influxdb influxdb3 create token --admin | grep "Token:" | awk '{print $2}' | tr -d '\r')
  echo "$TOKEN" > .influxdb3-token
  echo "Token guardado en .influxdb3-token"
else
  echo "El token ya existe localmente."
  TOKEN=$(cat .influxdb3-token)
fi

echo "Creando base de datos 'fixture2030' con retención de 30 días..."
docker compose exec -T influxdb influxdb3 create database fixture2030 --retention-period 30d --token "$TOKEN" || echo "La base de datos ya existe o hubo un error al crearla."

echo "=== Inicialización completa ==="

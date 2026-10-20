#!/bin/bash
set -euo pipefail

# Cambiar al directorio raíz del proyecto (donde está el docker-compose.yml de influxDB o el global)
cd "$(dirname "$0")/.."

echo "=== Inicializando InfluxDB 3 Core ==="

# Generar token si no existe
if [ ! -f .influxdb3-token ]; then
  echo "Creando token administrador..."
  # Se ejecuta el comando dentro del contenedor y se extrae el token
  if ! TOKEN=$(docker exec -i fixture2030-influxdb influxdb3 create token --admin | awk '/Token:/ {print $2}' | tr -d '\r'); then
    echo "No se pudo crear el token; recuperar la credencial del servidor existente." >&2
    exit 1
  fi
  [ -n "$TOKEN" ] || { echo "No se obtuvo un token. Recuperar el token del servidor existente; no se crea un archivo vacío." >&2; exit 1; }
  printf '%s\n' "$TOKEN" > .influxdb3-token
  echo "Token guardado en .influxdb3-token"
else
  echo "El token ya existe localmente."
  TOKEN=$(cat .influxdb3-token)
fi

[ -n "$TOKEN" ] || { echo "El archivo de token está vacío." >&2; exit 1; }

# Verificar HTTP además del código del CLI: este puede imprimir un error y salir 0.
DATABASES=$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8181/api/v3/configure/database)
if printf '%s' "$DATABASES" | grep -q '"fixture2030"'; then
  echo "Base fixture2030 existente y token aceptado."
  exit 0
fi

echo "Creando base de datos 'fixture2030' con retención de 30 días..."
docker exec -i fixture2030-influxdb influxdb3 create database fixture2030 --retention-period 30d --token "$TOKEN"

DATABASES=$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8181/api/v3/configure/database)
printf '%s' "$DATABASES" | grep -q '"fixture2030"' || { echo "No se verificó la base creada." >&2; exit 1; }

echo "=== Inicialización completa ==="

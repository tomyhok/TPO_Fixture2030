#!/usr/bin/env bash
# =====================================================================
# Hito 11 - El mismo diagnóstico, ejecutado DENTRO de la red de Docker Compose
# =====================================================================
# Reproduce el origen del modo contenedor de la API (docker-compose.api.yml):
# un contenedor con Python 3.12 y los mismos drivers (la imagen de la API del
# Hito 10) conectado a la red de las bases. Muestra que:
#   1. dentro de la red, cada base se alcanza por el NOMBRE DEL SERVICIO y el
#      PUERTO INTERNO (mongodb:27017, neo4j:7687, ...);
#   2. 127.0.0.1 dentro de un contenedor es el propio contenedor: la misma
#      configuración de la notebook falla (connection refused).
#
# Las credenciales llegan con --env-file (no aparecen en los argumentos) y el
# token de InfluxDB se monta de solo lectura. Los scripts se montan de solo
# lectura. El contenedor se elimina al terminar (--rm).
#
# Requisito: imagen de la API construida una vez, desde la raíz:
#   docker compose -f docker-compose.yml -f fixture2030-hito-10-api-integrada/docker-compose.api.yml build api
# Uso: bash scripts/evaluar_desde_red_docker.sh [--modo nativo|tcp] [--producto ...]
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

IMAGEN="${IMAGEN_API:-tpo_fixture2030-api}"
RED="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' fixture2030-mongodb 2> /dev/null | awk '{print $1}')"
TOKEN="$RAIZ/fixture2030-influxDB/.influxdb3-token"

if [ -z "$RED" ]; then echo "[SKIP] no se encontró la red de las bases (¿contenedores detenidos?)"; exit 0; fi
if ! docker image inspect "$IMAGEN" > /dev/null 2>&1; then
  echo "[SKIP] no existe la imagen $IMAGEN. Construirla con:"
  echo "  docker compose -f docker-compose.yml -f fixture2030-hito-10-api-integrada/docker-compose.api.yml build api"
  exit 0
fi
[ $# -eq 0 ] && set -- --modo nativo

correr() {  # etiqueta, variables -e..., -- args del evaluador
  docker run --rm --network "$RED" \
    --env-file "$(ruta_host "$HITO10/.env")" \
    -e INFLUX_TOKEN= -e INFLUX_TOKEN_FILE=/run/secrets/influx_token \
    -v "$(ruta_host "$TOKEN"):/run/secrets/influx_token:ro" \
    -v "$(ruta_host "$HITO/scripts"):/h11/scripts:ro" \
    -e PYTHONDONTWRITEBYTECODE=1 \
    "$@"
}

titulo "Diagnóstico desde la red Docker '$RED' (imagen $IMAGEN): hosts = nombres de servicio"
echo "Topología: contenedor efímero -> red $RED -> mongodb:27017, neo4j:7687/7474, cassandra:9042,"
echo "redis:6379, influxdb:8181, iris:1972/52773 (puertos INTERNOS; no pasan por los puertos publicados)."
correr \
  -e MONGO_HOST=mongodb -e NEO4J_URI=bolt://neo4j:7687 -e NEO4J_HTTP_URL=http://neo4j:7474 \
  -e CASSANDRA_HOSTS=cassandra -e REDIS_HOST=redis -e INFLUX_URL=http://influxdb:8181 \
  -e IRIS_HOST=iris -e IRIS_PORTAL_URL=http://iris:52773/csp/sys/UtilHome.csp \
  --entrypoint python "$IMAGEN" /h11/scripts/evaluar_conectividad.py "$@" \
  --etiqueta "origen: contenedor en la red $RED"

titulo "Misma configuración de la notebook (127.0.0.1) ejecutada dentro de un contenedor"
echo "Se espera connection refused: dentro del contenedor 127.0.0.1 es el propio contenedor, no la notebook."
correr \
  -e MONGO_HOST=127.0.0.1 -e REDIS_HOST=127.0.0.1 \
  --entrypoint python "$IMAGEN" /h11/scripts/evaluar_conectividad.py --modo tcp --producto mongodb,redis \
  --etiqueta "origen: contenedor con hosts de la notebook (configuración equivocada)"

#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Escenarios de configuración incorrecta y su corrección (RF17, RF20, 5.7)
# =====================================================================
# Parte A - diagnóstico nativo con UNA variable cambiada por entorno (no se
#   edita ningún archivo, no se toca ningún contenedor) y luego la misma
#   prueba con la configuración correcta:
#     A1 host incorrecto      MONGO_HOST=mongodb (nombre de servicio usado desde la notebook)
#     A2 puerto equivocado    NEO4J_URI=bolt://127.0.0.1:7474 (puerto HTTP en lugar de Bolt)
#     A3 puerto no publicado  REDIS_PORT=6380
#     A4 contexto inexistente CASSANDRA_KEYSPACE / NEO4J_DATABASE / INFLUX_DATABASE / IRIS_NAMESPACE
#     A5 credencial inválida  MONGO_PASSWORD incorrecta (MongoDB no bloquea cuentas; en IRIS no
#                             se prueba porque los logins fallidos deshabilitan el usuario)
#     A6 timeout muy bajo     TIMEOUT_OPERACION_S=0.001 en InfluxDB
# Parte B - la API ante la misma clase de errores: se levantan instancias
#   TEMPORALES de la API (puertos 8002 y 8003) con configuración errónea, se
#   prueban sus rutas y se detienen. La API principal (8000) no se toca.
#
# Uso: bash scripts/escenarios_configuracion.sh [A|B]   (sin argumento: ambas partes)
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"
PARTE="${1:-AB}"
TMP="$(mktemp -d)"
trap 'detener_puerto 8002; detener_puerto 8003; rm -rf "$TMP"' EXIT

caso() {  # titulo, producto, VAR=valor...
  local nombre="$1" producto="$2"; shift 2
  titulo "$nombre"
  echo "Cambio aplicado (solo para este proceso): $*"
  env "$@" "$PY" "$HITO/scripts/evaluar_conectividad.py" --modo nativo --producto "$producto" --sin-sondas \
    --etiqueta "$nombre" | sed -n '/^--- /,/^Total/p' | grep -vE '^\[OK  \] [a-z0-9]+ +(configuracion|contenedor)'
}

if [[ "$PARTE" == *A* ]]; then
  caso "A1 host incorrecto: nombre de servicio Docker desde la notebook" mongodb MONGO_HOST=mongodb
  caso "A2 puerto equivocado: Bolt apuntando al puerto HTTP 7474" neo4j NEO4J_URI=bolt://127.0.0.1:7474
  caso "A3 puerto no publicado: Redis en 6380" redis REDIS_PORT=6380
  caso "A4a contexto inexistente: keyspace de Cassandra" cassandra CASSANDRA_KEYSPACE=fixture2030_inexistente
  caso "A4b contexto inexistente: database de Neo4j" neo4j NEO4J_DATABASE=noexiste
  caso "A4c contexto inexistente: database de InfluxDB" influxdb INFLUX_DATABASE=fixture2030_inexistente
  caso "A4d contexto inexistente: database de MongoDB (MongoDB no da error)" mongodb MONGO_DATABASE=fixture2030_inexistente
  caso "A4e contexto inexistente: namespace de IRIS (IRIS responde Access Denied)" iris IRIS_NAMESPACE=NOEXISTE
  caso "A5 credencial inválida: MongoDB" mongodb MONGO_PASSWORD=incorrecta-de-prueba
  caso "A6 timeout configurado demasiado bajo: InfluxDB" influxdb TIMEOUT_OPERACION_S=0.001

  titulo "A7 corrección (RF20): misma evaluación con la configuración original"
  evaluar --modo nativo --sin-sondas --etiqueta "configuración corregida" | sed -n '/^Matriz/,/^Total/p'
fi

if [[ "$PARTE" == *B* ]]; then
  api_temporal() {  # puerto, VAR=valor...
    local puerto="$1"; shift
    detener_puerto "$puerto"
    (cd "$HITO10" && env "$@" HEALTH_CACHE_TTL_S=0 "$PY" -m uvicorn app.main:app --host 127.0.0.1 \
      --port "$puerto" --no-access-log > "$TMP/api_$puerto.log" 2>&1 &)
    esperar_url "http://127.0.0.1:$puerto/health/live" 40 || { echo "la API temporal no arrancó"; cat "$TMP/api_$puerto.log"; return 1; }
  }

  titulo "B1 API temporal (8002) con contexto/puertos incorrectos"
  B1=(MONGO_DATABASE=fixture2030_inexistente NEO4J_DATABASE=noexiste CASSANDRA_KEYSPACE=fixture2030_inexistente
      REDIS_PORT=6380 INFLUX_DATABASE=fixture2030_inexistente IRIS_PORT=1973)
  echo "Configuración de la instancia: ${B1[*]}"
  echo "(IRIS se rompe con un puerto no publicado y no con credenciales: un login fallido cuenta para el bloqueo)"
  if api_temporal 8002 "${B1[@]}"; then
    API_URL=http://127.0.0.1:8002 API_LOG_FILE="$TMP/api_8002.log" \
      evaluar --modo api --etiqueta "API con configuración errónea" | sed -n '/^--- API/,/^Total/p'
    echo; echo "# Log de la instancia temporal (resultado por dependencia y duración)"
    grep -E "adaptador|salud" "$TMP/api_8002.log" | grep -E "request_id=h11-" | head -25
  fi
  detener_puerto 8002

  titulo "B2 API temporal (8003) con TIMEOUT_OPERACION_S=0.001 (dependencia 'lenta')"
  if api_temporal 8003 TIMEOUT_OPERACION_S=0.001; then
    API_URL=http://127.0.0.1:8003 API_LOG_FILE="$TMP/api_8003.log" \
      evaluar --modo api --etiqueta "API con timeout de operación de 1 ms" | sed -n '/^--- API/,/^Total/p'
    echo; echo "# Log de la instancia temporal"
    grep -E "adaptador" "$TMP/api_8003.log" | grep -E "request_id=h11-" | head -15
  fi
  detener_puerto 8003
  echo; echo "Instancias temporales detenidas. La API principal y los datos no se modificaron."
fi

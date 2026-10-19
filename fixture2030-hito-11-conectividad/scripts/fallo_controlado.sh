#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Fallo controlado y reversible: MongoDB detenido (RF20, RF21, 5.7)
# =====================================================================
# 1. Condición inicial: estado del contenedor, volumen, conteo de documentos
#    y respuesta de la API.
# 2. Cambio: `docker stop fixture2030-mongodb` (NO `down`, NO `-v`: el volumen
#    y los datos no se tocan).
# 3. Pruebas durante la falla: diagnóstico por capas, rutas de la API con
#    request ID y tiempo, readiness/diagnóstico de la API y líneas de log.
# 4. Recuperación: `docker start` y espera activa hasta que el protocolo responda.
# 5. Resultado después de recuperar y verificación de datos/volumen conservados.
#
# Requisitos: bases levantadas y la API iniciada en API_URL (por defecto 8000).
# Uso: bash scripts/fallo_controlado.sh
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

API_URL="${API_URL:-http://127.0.0.1:8000}"
CONTENEDOR="${DOCKER_PREFIJO:-fixture2030-}mongodb"
LOG_API="$HITO10/logs/api.log"
CORRIDA="h11-fallo-$(date +%H%M%S)"

conteo_mongo() {
  MONGO_USR="$(leer_env MONGO_USER)" MONGO_PW="$(leer_env MONGO_PASSWORD)" \
    docker exec -e MONGO_USR -e MONGO_PW "$CONTENEDOR" sh -c \
    'mongosh --quiet --norc -u "$MONGO_USR" -p "$MONGO_PW" --authenticationDatabase admin fixture2030 --eval "print(\"equipos=\" + db.equipos.countDocuments({}) + \" jugadores=\" + db.jugadores.countDocuments({}))"' 2>&1 | tail -1
}
volumen() {
  docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Type}} {{.Name}} -> {{.Destination}}{{end}}{{end}}' "$CONTENEDOR"
  local nombre
  nombre="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Name}}{{end}}{{end}}' "$CONTENEDOR")"
  [ -n "$nombre" ] && docker volume inspect -f 'volumen {{.Name}} creado {{.CreatedAt}}' "$nombre"
}
log_de() {  # líneas del log de la API para los request IDs de esta corrida
  [ -f "$LOG_API" ] && grep -F "request_id=$CORRIDA" "$LOG_API" | tail -n "${1:-20}" || echo "(log de la API no encontrado en $LOG_API)"
}

if ! esperar_url "$API_URL/health/live" 5; then
  echo "La API no responde en $API_URL/health/live: iniciarla antes (bash ../fixture2030-hito-10-api-integrada/scripts/iniciar_api.sh)"
  exit 1
fi

titulo "1. Condición inicial"
docker inspect -f 'contenedor {{.Name}}: {{.State.Status}} (restart policy: {{.HostConfig.RestartPolicy.Name}})' "$CONTENEDOR"
volumen
ANTES_CONTEO="$(conteo_mongo)"; echo "datos: $ANTES_CONTEO"
ANTES_VOLUMEN="$(volumen | tail -1)"
api_get "$API_URL" "/equipos/ARG" "$CORRIDA-01"
api_get "$API_URL" "/health/dependencias?refrescar=true" "$CORRIDA-02"

titulo "2. Cambio aplicado: docker stop $CONTENEDOR (sin borrar contenedor ni volumen)"
inicio=$(date +%s)
docker stop "$CONTENEDOR"
echo "detenido en $(( $(date +%s) - inicio )) s"

titulo "3a. Diagnóstico por capas con MongoDB detenido"
evaluar --producto mongodb --modo completo --sin-sondas --etiqueta "fallo controlado: MongoDB detenido"

titulo "3b. Respuestas de la API durante la falla (request ID y tiempo de espera)"
echo "# Ruta de MongoDB: se espera 503 DEPENDENCIA_NO_DISPONIBLE (o 504 si el rechazo tarda más que el timeout)"
api_get "$API_URL" "/equipos/ARG" "$CORRIDA-03"
echo; echo "# Ruta de otro módulo (Neo4j): debe seguir funcionando -> la falla queda aislada"
api_get "$API_URL" "/partidos/P-001/eventos?limit=2" "$CORRIDA-04"
echo; echo "# Readiness: 200 con mongodb en no_disponibles (las demás fuentes atienden)"
api_get "$API_URL" "/health/ready" "$CORRIDA-05"
echo; echo "# Diagnóstico por dependencia (refrescado)"
api_get "$API_URL" "/health/dependencias?refrescar=true" "$CORRIDA-06"
echo; echo "# Chequeo del Hito 10: 503 indicando la fuente"
api_get "$API_URL" "/health" "$CORRIDA-07"
sleep 0.5
echo; echo "# Líneas del log de la API para estas requests (sin secretos: ruta, dependencia, resultado, duración)"
log_de 30

titulo "4. Recuperación: docker start $CONTENEDOR"
docker start "$CONTENEDOR"
inicio=$(date +%s%3N)
recuperado=0
for _ in $(seq 1 60); do
  if evaluar --producto mongodb --modo nativo --capas protocolo --estricto > /dev/null 2>&1; then recuperado=1; break; fi
  sleep 1
done
echo "protocolo MongoDB disponible: $([ $recuperado = 1 ] && echo sí || echo NO) tras $(( $(date +%s%3N) - inicio )) ms"

titulo "5. Resultado después de recuperar (RF20: misma prueba, nuevo estado)"
evaluar --producto mongodb --modo completo --sin-sondas --etiqueta "fallo controlado: MongoDB recuperado"
api_get "$API_URL" "/equipos/ARG" "$CORRIDA-08"
api_get "$API_URL" "/health/dependencias?refrescar=true" "$CORRIDA-09"
sleep 0.5
echo; log_de 6

titulo "6. Datos y volumen conservados"
DESPUES_CONTEO="$(conteo_mongo)"
DESPUES_VOLUMEN="$(volumen | tail -1)"
echo "antes:   $ANTES_CONTEO | $ANTES_VOLUMEN"
echo "después: $DESPUES_CONTEO | $DESPUES_VOLUMEN"
if [ "$ANTES_CONTEO" = "$DESPUES_CONTEO" ] && [ "$ANTES_VOLUMEN" = "$DESPUES_VOLUMEN" ]; then
  echo "OK: mismos documentos y mismo volumen (no se borró ni recreó nada)"
else
  echo "ATENCIÓN: los conteos o el volumen difieren"
fi

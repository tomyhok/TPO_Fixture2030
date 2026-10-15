#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Generar la evidencia de funcionamiento (RF17)
# =====================================================================
# Ejecuta escenarios reales con cURL contra la API levantada y guarda la
# request, el estado, los headers relevantes y el cuerpo de cada respuesta
# en docs/evidencia/. Ningún escenario envía ni muestra credenciales.
#
# Requisitos: contenedores levantados, scripts/preparar_datos.sh ejecutado
# y la API corriendo con scripts/iniciar_api.sh (escribe logs/api.log).
#
# Uso (desde fixture2030-hito-10-api-integrada/):
#   bash scripts/generar_evidencia.sh               escenarios + pruebas + latencia
#   bash scripts/generar_evidencia.sh --con-caida   además detiene Redis ~10 s y lo
#                                                   vuelve a iniciar (sus datos persisten en AOF)
# =====================================================================
set -uo pipefail
# Python lee y escribe UTF-8 aunque la consola de Windows use otra página de códigos.
export PYTHONIOENCODING=utf-8
HITO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HITO"
PY=".venv/Scripts/python"; [ -x "$PY" ] || PY=".venv/bin/python"
B="http://127.0.0.1:$(grep -E '^API_PORT=' .env | cut -d= -f2 | tr -d '\r')"
E=docs/evidencia
mkdir -p "$E"
JSON='Content-Type: application/json'
uuid() { "$PY" -c "import uuid; print(uuid.uuid4())"; }

curl -s -o /dev/null "$B/health" || { echo "La API no responde en $B: iniciarla con scripts/iniciar_api.sh"; exit 1; }

encabezado() { echo "# $1"; echo "# Generado: $(date -u '+%Y-%m-%dT%H:%M:%SZ') con scripts/generar_evidencia.sh"; echo "# API: $B (notebook)"; echo; }

# caso "descripción" MÉTODO ruta [args de curl...]
caso() {
  local desc="$1" metodo="$2" ruta="$3"; shift 3
  echo "------------------------------------------------------------------"
  echo "## $desc"
  printf '$ curl -i -X %s %q' "$metodo" "$B$ruta"; [ $# -gt 0 ] && printf ' %q' "$@"; echo
  echo
  curl -s -i -X "$metodo" "$B$ruta" "$@" | tr -d '\r' | grep -v -i -E '^(date|server|content-length):'
  echo; echo
}

echo "[0] Ambiente"
{
  encabezado "Ambiente de ejecución"
  echo "> git"; git log -1 --format='commit %h (%ad)' --date=iso 2>/dev/null; echo
  echo "> Sistema y Python"; "$PY" -c "import platform; print(platform.platform(), '| Python', platform.python_version())"; echo
  echo "> Docker"; docker version --format 'Docker Engine {{.Server.Version}}'; echo
  echo "> Contenedores"; docker ps --filter "name=fixture2030-" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"; echo
  echo "> Dependencias de la API"; grep -v '^#' requirements.txt | grep -v '^$'
} > "$E/00_ambiente.txt" 2>&1

echo "[1] Conectividad"
{ encabezado "Conectividad de las seis fuentes"; bash scripts/verificar_conectividad.sh; echo; caso "CU16 - /health con todas las fuentes" GET /health; } > "$E/01_conectividad.txt" 2>&1

echo "[2] MongoDB"
{
  encabezado "MongoDB - equipos y jugadores (CU01-CU04)"
  caso "CU01 ficha de una selección" GET /equipos/ARG
  caso "CU01 selección inexistente -> 404" GET /equipos/XYZ
  caso "CU02 listado paginado por ranking, filtro por confederación" GET "/equipos?confederacion=CONMEBOL&page=1&size=3"
  caso "CU02 página fuera de rango -> 200 vacío" GET "/equipos?page=3&size=50"
  caso "CU03 plantel filtrado por posición" GET "/equipos/ARG/jugadores?posicion=ARQ"
  caso "CU03 plantel de selección inexistente -> 404" GET /equipos/XYZ/jugadores
  caso "CU04 ficha de un jugador" GET /jugadores/ARG-10
} > "$E/02_mongodb.txt" 2>&1

echo "[3] Neo4j"
docker exec fixture2030-redis redis-cli DEL cache:partido:P-001 > /dev/null
{
  encabezado "Neo4j - partidos, eventos y relaciones (CU05-CU07), con caché Redis"
  caso "CU05 ficha del partido, primera lectura -> X-Cache: MISS (Neo4j)" GET /partidos/P-001
  caso "CU05 segunda lectura -> X-Cache: HIT (Redis)" GET /partidos/P-001
  echo "> TTL de la entrada de caché"; docker exec fixture2030-redis redis-cli TTL cache:partido:P-001; echo
  caso "CU05 partido inexistente -> 404" GET /partidos/P-999
  caso "CU06 eventos con protagonista" GET /partidos/P-001/eventos
  caso "CU06 partido sin eventos -> 200 con lista vacía" GET /partidos/P-002/eventos
  caso "CU06 partido inexistente -> 404" GET /partidos/P-999/eventos
  caso "CU07 rivales de una selección" GET "/equipos/ARG/rivales?limit=10"
} > "$E/03_neo4j.txt" 2>&1

echo "[4] Cassandra"
K1=$(uuid)
TEXTO="Evidencia Hito 10 $(date -u +%Y%m%dT%H%M%S): que golazo"
CUERPO='{"id_usuario":"U-1001","usuario_alias":"hincha_albiceleste","equipo_apoyado":"ARG","texto":"'"$TEXTO"'","idioma":"es","minuto_partido":67}'
{
  encabezado "Cassandra - comentarios (CU08-CU09)"
  caso "CU08 muro de una ventana, página 1 (limit=3)" GET "/partidos/P-001/comentarios?ventana=203006152015&limit=3"
  CURSOR=$(curl -s "$B/partidos/P-001/comentarios?ventana=203006152015&limit=3" | "$PY" -c "import sys,json; print(json.load(sys.stdin)['cursor_siguiente'])")
  caso "CU08 página 2 con el cursor_siguiente" GET "/partidos/P-001/comentarios?ventana=203006152015&limit=3&cursor=$CURSOR"
  caso "CU08 ventana sin comentarios -> 200 vacío" GET "/partidos/P-001/comentarios?ventana=203001010000"
  caso "CU09 publicar comentario -> 201" POST /partidos/P-001/comentarios -H "$JSON" -H "Idempotency-Key: $K1" -d "$CUERPO"
  caso "CU09 reintento con la misma Idempotency-Key -> 200 Idempotent-Replayed" POST /partidos/P-001/comentarios -H "$JSON" -H "Idempotency-Key: $K1" -d "$CUERPO"
  caso "CU09 misma clave con otro cuerpo -> 409" POST /partidos/P-001/comentarios -H "$JSON" -H "Idempotency-Key: $K1" -d "${CUERPO/67/68}"
  caso "CU09 partido inexistente -> 404" POST /partidos/P-999/comentarios -H "$JSON" -H "Idempotency-Key: $(uuid)" -d "$CUERPO"
  echo "> Comprobación directa en Cassandra: el comentario existe una sola vez en el historial del usuario"
  echo "  (consulta acotada a la partición (id_usuario, periodo) del Hito 6)"
  docker exec fixture2030-cassandra cqlsh -e "SELECT id_comentario, id_partido, texto FROM fixture2030.comentarios_por_usuario WHERE id_usuario='U-1001' AND periodo='$(date -u +%Y%m)' AND texto='$TEXTO' ALLOW FILTERING;"
} > "$E/04_cassandra.txt" 2>&1

echo "[5] Redis"
{
  encabezado "Redis - sesiones (CU10-CU11)"
  docker exec fixture2030-redis redis-cli HSET sesion:S-7001 id_sesion S-7001 usuario_id U-7001 rol fan estado activa dispositivo web paginas_vistas 4 > /dev/null
  docker exec fixture2030-redis redis-cli EXPIRE sesion:S-7001 600 > /dev/null
  docker exec fixture2030-redis redis-cli HSET sesion:S-7002 usuario_id U-7002 rol fan estado activa > /dev/null
  docker exec fixture2030-redis redis-cli EXPIRE sesion:S-7002 2 > /dev/null
  echo "> Preparación: sesion:S-7001 (TTL 600 s) y sesion:S-7002 (TTL 2 s) creadas con redis-cli"; echo
  caso "CU10 sesión vigente (no expone dispositivo ni paginas_vistas)" GET /sesiones/S-7001
  caso "CU10 S-7002 antes de expirar" GET /sesiones/S-7002
  sleep 3
  caso "CU10 S-7002 después de 3 s -> 404 SESION_NO_VIGENTE" GET /sesiones/S-7002
  caso "CU11 cerrar sesión -> 204" DELETE /sesiones/S-7001
  caso "CU11 cerrar otra vez -> 204 (idempotente)" DELETE /sesiones/S-7001
  caso "CU10 sesión cerrada -> 404" GET /sesiones/S-7001
} > "$E/05_redis.txt" 2>&1

echo "[6] InfluxDB"
{
  encabezado "InfluxDB - estadísticas temporales (CU12)"
  caso "CU12 ventana de 15 min a 5m, ambos equipos" GET "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z&resolucion=5m"
  caso "CU12 un equipo a 1m" GET "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:03:00Z&resolucion=1m&equipo=ARG"
  echo "> Ventana máxima (3 h) a 10s: cantidad de puntos devueltos"
  curl -s "$B/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T23:00:00Z&resolucion=10s" \
    | "$PY" -c "import sys,json; d=json.load(sys.stdin); print({s['equipo']: len(s['puntos']) for s in d['series']}, '(tope: 1081 por equipo; hay 2 h de datos)')"
  echo
  caso "CU12 ventana sin puntos -> 200 series vacías" GET "/partidos/P-001/estadisticas?desde=2031-01-01T00:00:00Z&hasta=2031-01-01T01:00:00Z"
  caso "CU12 intervalo invertido -> 400" GET "/partidos/P-001/estadisticas?desde=2030-06-10T22:00:00Z&hasta=2030-06-10T20:00:00Z"
  caso "CU12 intervalo mayor a 3 h -> 400" GET "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-11T20:00:00Z"
  caso "CU12 fecha sin zona horaria -> 400" GET "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00&hasta=2030-06-10T21:00:00"
} > "$E/06_influxdb.txt" 2>&1

echo "[7] IRIS"
docker exec -i fixture2030-iris iris session IRIS -U USER > /dev/null <<'EOF'
Write ##class(Fixture.API).CargarMuestra(),!
Halt
EOF
K2=$(uuid)
{
  encabezado "IRIS - actas oficiales (CU13-CU15). Actas reiniciadas con Fixture.API.CargarMuestra()"
  caso "CU13 acta de un partido en juego" GET /partidos-oficiales/P-001
  caso "CU13 acta inexistente -> 404" GET /partidos-oficiales/P-999
  caso "CU14 transición inválida Programado -> Finalizado -> 409" PATCH /partidos-oficiales/P-002/estado -H "$JSON" -d '{"estado":"Finalizado"}'
  caso "CU14 Programado -> En Juego -> 200 cambiado:true" PATCH /partidos-oficiales/P-002/estado -H "$JSON" -d '{"estado":"En Juego"}'
  caso "CU14 repetir En Juego -> 200 cambiado:false (idempotente)" PATCH /partidos-oficiales/P-002/estado -H "$JSON" -d '{"estado":"En Juego"}'
  caso "CU15 registrar evento -> 201" POST /partidos-oficiales/P-002/eventos -H "$JSON" -H "Idempotency-Key: $K2" -d '{"minuto":12,"tipo":"Gol","descripcion":"Gol de URU-9"}'
  caso "CU15 reintento con la misma clave -> 200 sin duplicar" POST /partidos-oficiales/P-002/eventos -H "$JSON" -H "Idempotency-Key: $K2" -d '{"minuto":12,"tipo":"Gol","descripcion":"Gol de URU-9"}'
  caso "CU15 evento en partido Finalizado (P-003) -> 409 por %OnBeforeSave" POST /partidos-oficiales/P-003/eventos -H "$JSON" -H "Idempotency-Key: $(uuid)" -d '{"minuto":90,"tipo":"Gol"}'
  caso "CU15 minuto fuera de rango -> 400 (antes de llegar a IRIS)" POST /partidos-oficiales/P-002/eventos -H "$JSON" -H "Idempotency-Key: $(uuid)" -d '{"minuto":0,"tipo":"Gol"}'
} > "$E/07_iris.txt" 2>&1

echo "[8] Validación y errores generales"
{
  encabezado "Validación y formato de error común"
  caso "Parámetro de ruta con formato inválido -> 400 (no se consulta la base)" GET /equipos/arg
  caso "Query fuera de rango -> 400" GET "/equipos?size=500"
  caso "Cuerpo con campos faltantes y extra -> 400" POST /partidos/P-001/comentarios -H "$JSON" -H "Idempotency-Key: $(uuid)" -d '{"texto":"","campo_extra":1}'
  caso "Falta Idempotency-Key -> 400" POST /partidos/P-001/comentarios -H "$JSON" -d "$CUERPO"
  caso "Ruta inexistente -> 404 con el formato común" GET /no-existe
  caso "Método no permitido -> 405" PUT /equipos/ARG
  caso "X-Request-ID enviado por el cliente se reutiliza" GET /equipos/XYZ -H "X-Request-ID: evidencia-hito10-001"
} > "$E/08_validacion_y_errores.txt" 2>&1

if [ "${1:-}" = "--con-caida" ]; then
  echo "[9] Dependencia caída (Redis detenido)"
  {
    encabezado "Dependencia caída: docker stop fixture2030-redis"
    echo "> docker stop fixture2030-redis"; docker stop fixture2030-redis; echo
    caso "CU10 con Redis caído -> 503/504, nunca 200 vacío" GET /sesiones/S-0001
    caso "CU05 con Redis caído -> 200 degradado X-Cache: BYPASS (lee Neo4j)" GET /partidos/P-002
    caso "CU09 con Redis caído -> no se escribe sin garantía de idempotencia" POST /partidos/P-001/comentarios -H "$JSON" -H "Idempotency-Key: $(uuid)" -d "$CUERPO"
    caso "CU16 /health con Redis caído -> 503 indicando la fuente" GET /health
    echo "> docker start fixture2030-redis"; docker start fixture2030-redis; sleep 3; echo
    caso "CU10 Redis de nuevo disponible -> la API se recupera sin reiniciarse" GET /sesiones/S-0001
  } > "$E/09_dependencia_caida.txt" 2>&1
fi

if curl -s -o /dev/null "http://127.0.0.1:8001/health"; then
  echo "[9b] API en contenedor (puerto 8001)"
  {
    B_NOTEBOOK="$B"; B="http://127.0.0.1:8001"
    encabezado "Modo contenedor: docker-compose.api.yml (hosts = nombres de servicio)" | sed 's/(notebook)/(contenedor fixture2030-api)/'
    echo "> Variables de conexión del contenedor (sin secretos)"
    docker exec fixture2030-api env | grep -E '^(MONGO_HOST|NEO4J_URI|CASSANDRA_HOSTS|REDIS_HOST|INFLUX_URL|IRIS_HOST)=' | sort
    echo
    caso "CU16 /health desde el contenedor" GET /health
    caso "CU13 acta desde el contenedor" GET /partidos-oficiales/P-001
    B="$B_NOTEBOOK"
  } > "$E/14_modo_contenedor.txt" 2>&1
fi

echo "[10] Correlación de logs"
RID="evidencia-correlacion-$(date +%s)"
curl -s -o /dev/null -H "$JSON" -H "Idempotency-Key: $(uuid)" -H "X-Request-ID: $RID" \
  -X POST "$B/partidos/P-001/comentarios" -d "${CUERPO/que golazo/correlacion de logs}"
curl -s -o /dev/null -H "X-Request-ID: $RID-iris" -H "$JSON" -H "Idempotency-Key: $(uuid)" \
  -X POST "$B/partidos-oficiales/P-003/eventos" -d '{"minuto":90,"tipo":"Gol"}'
sleep 1
{
  encabezado "Correlación entre la respuesta y los logs (RF18, RNF10)"
  echo "Se enviaron dos requests con X-Request-ID propio. Líneas de logs/api.log con ese identificador:"
  echo "(ruta, método, dependencia, operación, resultado y duración; sin cuerpos ni credenciales)"
  echo
  echo "> POST /partidos/P-001/comentarios  X-Request-ID: $RID"
  grep "request_id=$RID " logs/api.log
  echo
  echo "> POST /partidos-oficiales/P-003/eventos  X-Request-ID: $RID-iris"
  grep "request_id=$RID-iris " logs/api.log
  echo
  echo "> Búsqueda de secretos en logs/api.log (password|token|secret): $(grep -c -i -E 'password|token|secret' logs/api.log) coincidencias"
} > "$E/10_logs_correlacion.txt" 2>&1

echo "[11] Pruebas automatizadas"
{ encabezado "pytest: unitarias + integración"; "$PY" -m pytest -v -p no:cacheprovider 2>&1; } > "$E/11_pruebas.txt"

echo "[12] Latencia"
"$PY" scripts/medir_latencia.py --base "$B" --n 200 --salida "$E/12_latencia.md" > /dev/null

echo "[13] Contrato"
{
  encabezado "Contrato OpenAPI y Swagger UI"
  echo "> GET /docs (Swagger UI): HTTP $(curl -s -o /dev/null -w '%{http_code}' "$B/docs")"
  echo "> GET /openapi.json servido por la API vs. openapi/openapi.yaml versionado:"
  curl -s "$B/openapi.json" | "$PY" -c "
import sys, json, yaml
servido = json.load(sys.stdin)
archivo = yaml.safe_load(open('openapi/openapi.yaml', encoding='utf-8'))
servido['servers'] = archivo['servers']  # el server depende del API_PORT local
print('  idénticos' if servido == archivo else '  DIFERENTES: regenerar con scripts/exportar_openapi.py')
print('  rutas:', len(archivo['paths']), '| operaciones:', sum(len(v) for v in archivo['paths'].values()))
for ruta, ops in archivo['paths'].items():
    for metodo, op in ops.items():
        print(f'  {metodo.upper():6} {ruta:48} {\" \".join(op[\"responses\"])}')
"
} > "$E/13_contrato.txt" 2>&1

if command -v npx > /dev/null; then
  echo "[15] Colección Postman (Newman)"
  { encabezado "Colección Postman ejecutada con Newman (scripts/ejecutar_postman.sh)"; bash scripts/ejecutar_postman.sh 2>&1 | grep -v '^npm notice'; } > "$E/15_postman_newman.txt"
fi

echo "Evidencia generada en $E/"

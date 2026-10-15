#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Preparar las fuentes de datos para la API
# =====================================================================
# Deja las seis bases con los datos de muestra que usan la API y las
# pruebas. Todos los pasos son idempotentes: reutilizan los scripts de los
# hitos anteriores (upsert / MERGE / IF NOT EXISTS / HSET) y no borran
# datos existentes, salvo los partidos de muestra P-001..P-003 del acta de
# IRIS, que se reinician a un estado conocido.
#
# Requisitos: contenedores levantados con `docker compose up -d` desde la
# raíz del repositorio y un archivo .env (copiado de .env.example).
#
# Uso (desde fixture2030-hito-10-api-integrada/):
#   bash scripts/preparar_datos.sh
# =====================================================================
set -euo pipefail

# Git Bash convierte /rutas en rutas de Windows al pasarlas a docker; las rutas
# de este script que van a docker son del contenedor, así que se desactiva solo ahí.
docker() { MSYS_NO_PATHCONV=1 command docker "$@"; }

HITO="$(cd "$(dirname "$0")/.." && pwd)"
RAIZ="$(cd "$HITO/.." && pwd)"
PY="$HITO/.venv/Scripts/python"
[ -x "$PY" ] || PY="$HITO/.venv/bin/python"

# Ruta del host para docker cp (en Git Bash hay que pasarla en formato Windows).
ruta_host() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

# Lee una variable del .env sin ejecutarlo (no se imprime nunca su valor).
leer_env() { grep -E "^$1=" "$HITO/.env" | head -1 | cut -d= -f2- | tr -d '\r'; }

[ -f "$HITO/.env" ] || { echo "Falta .env: copiar .env.example a .env y completarlo."; exit 1; }
IRIS_USER="$(leer_env IRIS_USER)"
IRIS_PASSWORD="$(leer_env IRIS_PASSWORD)"
NEO4J_PASSWORD="$(leer_env NEO4J_PASSWORD)"
case "$IRIS_PASSWORD" in ""|"<completar>"|*\"*) echo "IRIS_PASSWORD vacía, sin completar o con comillas en .env"; exit 1;; esac

paso() { echo; echo "=== $1 ==="; }

paso "1/6 MongoDB: verificar la carga del Hito 4"
docker exec fixture2030-mongodb mongosh --quiet -u "$(leer_env MONGO_USER)" -p "$(leer_env MONGO_PASSWORD)" \
  --authenticationDatabase admin fixture2030 \
  --eval 'print("equipos=" + db.equipos.countDocuments() + " jugadores=" + db.jugadores.countDocuments())'
echo "(Si los conteos son 0, ejecutar 02-carga.js como indica el README raíz.)"

paso "2/6 Neo4j: restricciones y carga del Hito 5"
docker cp "$(ruta_host "$RAIZ/fixture2030-mongoDB/init-scripts/data/equipos.json")" fixture2030-neo4j:/var/lib/neo4j/import/
docker cp "$(ruta_host "$RAIZ/fixture2030-mongoDB/init-scripts/data/jugadores.json")" fixture2030-neo4j:/var/lib/neo4j/import/
for f in estructura carga; do
  docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" < "$RAIZ/fixture2030-neo4j/queries/$f.cypher" > /dev/null
  echo "$f.cypher ok"
done

paso "3/6 Cassandra: keyspace, tablas y muestra del Hito 6"
for f in 01-keyspace 02-tablas 03-carga-muestra; do
  docker exec fixture2030-cassandra cqlsh -f "/scripts/$f.cql" > /dev/null
  echo "$f.cql ok"
done

paso "4/6 Redis: sesiones y caché de muestra del Hito 7"
docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli" > /dev/null
echo "carga_muestra.redis ok (sesiones S-0001..S-0010 con TTL de 1800 s)"

paso "5/6 InfluxDB: base y token del Hito 8 + partidos P-001 y P-002"
bash "$RAIZ/fixture2030-influxDB/scripts/inicializacion.sh" 2>&1 | grep -v -i token || true
"$PY" "$HITO/scripts/datos/cargar_estadisticas_influx.py"

paso "6/6 IRIS: clases, fachada, usuario de la API y actas de muestra"
docker cp "$(ruta_host "$HITO/iris/Fixture.API.cls")" fixture2030-iris:/tmp/Fixture.API.cls
docker exec -i fixture2030-iris iris session IRIS -U USER > /dev/null <<'EOF'
Do $system.OBJ.Load("/scripts/Fixture.Clases.cls","ck")
Do $system.OBJ.Load("/tmp/Fixture.API.cls","ck")
Halt
EOF
echo "Fixture.Clases.cls y Fixture.API.cls compiladas"

# Rol mínimo: base USER y ejecución de métodos de clase por la Native API.
# La contraseña viaja por stdin al contenedor; no queda en el historial ni en logs.
docker exec -i fixture2030-iris iris session IRIS -U %SYS > /dev/null <<EOF
If '##class(Security.Roles).Exists("FixtureAPI") Do ##class(Security.Roles).Create("FixtureAPI","Rol minimo de la API del Hito 10","%Native_ClassExecution:U","%DB_USER")
If ##class(Security.Users).Exists("$IRIS_USER") { Set p("Password")="$IRIS_PASSWORD",p("Roles")="FixtureAPI",p("ChangePassword")=0,p("Enabled")=1 Do ##class(Security.Users).Modify("$IRIS_USER",.p) }
If '##class(Security.Users).Exists("$IRIS_USER") Do ##class(Security.Users).Create("$IRIS_USER","FixtureAPI","$IRIS_PASSWORD","API REST Hito 10","USER","","",0,1)
Halt
EOF
echo "usuario $IRIS_USER con rol FixtureAPI ok"

docker exec -i fixture2030-iris iris session IRIS -U USER <<'EOF' | grep '"ok"'
Write ##class(Fixture.API).CargarMuestra(),!
Halt
EOF

echo
echo "Fuentes preparadas. Verificar con: bash scripts/verificar_conectividad.sh"

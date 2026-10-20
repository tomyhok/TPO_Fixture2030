#!/usr/bin/env bash
# Reutiliza muestras H4–H9. No borra conjuntos ni reinicia actas.
# Las muestras de Mongo/Neo/Cassandra/Redis con igual ID pueden actualizarse.
# Requiere .env completo. La falta de token InfluxDB es un error, no un éxito parcial oculto.
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
case "$IRIS_PASSWORD" in ""|"<completar>"|*\"*|*\$*|*\\*) echo "IRIS_PASSWORD vacía, sin completar o con comillas en .env"; exit 1;; esac

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

paso "4/6 Redis: muestra del módulo de muestra del Hito 7"
docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli" > /dev/null
echo "carga_muestra.redis ok (sesiones S-0001..S-0010 con TTL de 1800 s)"


paso "5/6 IRIS: clases del Hito 9 y muestra P-009 (se conserva si existe)"
docker exec -i fixture2030-iris iris session IRIS -U USER <<'EOF'
Do $SYSTEM.OBJ.Load("/scripts/Fixture.Clases.cls","ck")
Do $SYSTEM.OBJ.Load("/scripts/DemoOperaciones.mac","ck")
Do ^DemoOperaciones
Halt
EOF
# Identidad dedicada: solo crear si no existe. No cambiar una contraseña existente.
case "$IRIS_USER" in *[!a-zA-Z0-9_]*|"") echo "IRIS_USER inválido"; exit 1;; esac
docker exec -i fixture2030-iris iris session IRIS -U %SYS > /dev/null <<EOF
If '##class(Security.Roles).Exists("FixtureAPIRead") Do ##class(Security.Roles).Create("FixtureAPIRead","Lectura SQL del Hito 10","%Native_ClassExecution:U,%DB_USER:R")
If '##class(Security.Users).Exists("$IRIS_USER") Do ##class(Security.Users).Create("$IRIS_USER","FixtureAPIRead","$IRIS_PASSWORD","API local de lectura","USER","","",0,1)
Halt
EOF
docker exec -i fixture2030-iris iris session IRIS -U USER <<'EOF'
Do $SYSTEM.SQL.Execute("GRANT SELECT ON SCHEMA Fixture TO FixtureAPIRead").%Display()
Halt
EOF

paso "6/6 InfluxDB: cargar muestra únicamente con token válido ya configurado"
# No regenerar el token de un servidor existente ni ocultar fallos con '|| true'.
"$PY" "$HITO/scripts/datos/cargar_estadisticas_influx.py"
echo "Preparación finalizada. Verificar las seis lecturas y /health/dependencias."

#!/usr/bin/env bash
# =====================================================================
# Hito 11 - CLI nativos dentro del contenedor de cada producto
# =====================================================================
# ORIGEN: el propio contenedor del producto. Ahí "localhost" es el producto,
# no la notebook: esta prueba confirma que el producto responde a su cliente
# oficial, pero NO prueba el puerto publicado ni el camino que usa la API.
# Si esto da OK y el diagnóstico desde la notebook falla, el problema está en
# la publicación del puerto, el host o la configuración de la API.
#
# Las contraseñas viajan como variables de entorno del proceso docker
# (`-e VARIABLE` sin valor): no aparecen en los argumentos ni en la salida.
# Solo lecturas; no se modifica ningún dato.
#
# Uso: bash scripts/clientes_en_contenedor.sh [mongodb|neo4j|cassandra|redis|influxdb|iris ...]
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

PREFIJO="${DOCKER_PREFIJO:-fixture2030-}"
productos=("$@")
[ ${#productos[@]} -eq 0 ] && productos=(mongodb neo4j cassandra redis influxdb iris)

if ! command -v docker > /dev/null; then
  echo "[SKIP] docker CLI no disponible: no se pueden ejecutar los clientes dentro de los contenedores"
  exit 0
fi

ejecutar() {  # nombre, comando...
  local nombre="$1"; shift
  local contenedor="$PREFIJO$nombre" inicio fin salida codigo
  if [ "$(docker inspect -f '{{.State.Running}}' "$contenedor" 2> /dev/null)" != "true" ]; then
    echo "[SKIP] $nombre: el contenedor $contenedor no está en ejecución"
    return
  fi
  inicio=$(date +%s%3N)
  salida="$("$@" 2>&1)"; codigo=$?
  fin=$(date +%s%3N)
  if [ $codigo -eq 0 ]; then echo "[OK]   $nombre ($((fin - inicio)) ms, origen: contenedor $contenedor)"
  else echo "[FAIL] $nombre ($((fin - inicio)) ms, código $codigo, origen: contenedor $contenedor)"; fi
  echo "$salida" | sed 's/^/       /' | head -20
}

titulo "Clientes nativos dentro de los contenedores (origen: contenedor de cada producto)"

for p in "${productos[@]}"; do
  case "$p" in
    mongodb)
      echo; echo "\$ mongosh (usuario de .env, database fixture2030): ping + lectura de equipos"
      MONGO_USR="$(leer_env MONGO_USER)" MONGO_PW="$(leer_env MONGO_PASSWORD)" \
        ejecutar mongodb docker exec -e MONGO_USR -e MONGO_PW "${PREFIJO}mongodb" sh -c \
        'mongosh --quiet --norc -u "$MONGO_USR" -p "$MONGO_PW" --authenticationDatabase admin fixture2030 --eval "
          const p = db.runCommand({ping: 1});
          const e = db.equipos.findOne({_id: \"ARG\"}, {nombre: 1});
          print(\"version=\" + db.version() + \" ping.ok=\" + p.ok + \" db=\" + db.getName()
            + \" equipos=\" + db.equipos.estimatedDocumentCount() + \" ARG=\" + (e ? e.nombre : null)
            + \" inexistente=\" + db.equipos.findOne({_id: \"ZZZ\"}));"'
      ;;
    neo4j)
      echo; echo "\$ cypher-shell -a bolt://localhost:7687 -d neo4j --param 'codigo => \"P-001\"' (credenciales por NEO4J_USERNAME/NEO4J_PASSWORD)"
      NEO4J_USERNAME="$(leer_env NEO4J_USER)" NEO4J_PASSWORD="$(leer_env NEO4J_PASSWORD)" \
        ejecutar neo4j docker exec -e NEO4J_USERNAME -e NEO4J_PASSWORD "${PREFIJO}neo4j" \
        cypher-shell -a bolt://localhost:7687 -d neo4j --format plain --param 'codigo => "P-001"' \
        'MATCH (p:Partido {codigo_partido: $codigo}) OPTIONAL MATCH (e:Equipo)-[:DISPUTA]->(p) RETURN p.codigo_partido AS codigo, toString(p.fecha) AS fecha, collect(e.codigo_iso) AS equipos LIMIT 1'
      ;;
    cassandra)
      echo; echo "\$ cqlsh -k fixture2030: lectura con la clave de partición completa"
      ejecutar cassandra docker exec "${PREFIJO}cassandra" cqlsh -k fixture2030 -e \
        "SELECT id_partido, ventana, shard, usuario_alias, creado_en FROM comentarios_por_partido WHERE id_partido='P-001' AND ventana='203006152015' AND shard=1 LIMIT 3;"
      ;;
    redis)
      echo; echo "\$ redis-cli PING / EXISTS / PTTL / INFO keyspace"
      ejecutar redis docker exec "${PREFIJO}redis" sh -c \
        'echo "PING=$(redis-cli PING) EXISTS sesion:S-0001=$(redis-cli EXISTS sesion:S-0001) PTTL=$(redis-cli PTTL sesion:S-0001)"; redis-cli INFO keyspace | tr -d "\r" | grep "^db"'
      ;;
    influxdb)
      echo; echo "\$ influxdb3 query --database fixture2030 (token por INFLUXDB3_AUTH_TOKEN)"
      token_archivo="$RAIZ/fixture2030-influxDB/.influxdb3-token"
      INFLUXDB3_AUTH_TOKEN="$(leer_env INFLUX_TOKEN)"
      [ -z "$INFLUXDB3_AUTH_TOKEN" ] && [ -f "$token_archivo" ] && INFLUXDB3_AUTH_TOKEN="$(tr -d '\r\n' < "$token_archivo")"
      INFLUXDB3_AUTH_TOKEN="$INFLUXDB3_AUTH_TOKEN" ejecutar influxdb docker exec -e INFLUXDB3_AUTH_TOKEN "${PREFIJO}influxdb" \
        influxdb3 query --database fixture2030 \
        "SELECT COUNT(*) AS puntos, MIN(time) AS primero, MAX(time) AS ultimo FROM estadisticas_partido WHERE partido_id = 'P-001' AND time >= '2030-06-10T20:00:00Z' AND time < '2030-06-10T20:15:00Z'"
      unset INFLUXDB3_AUTH_TOKEN
      ;;
    iris)
      echo; echo "\$ iris session IRIS -U USER (terminal del contenedor, autenticación del sistema operativo)"
      ejecutar iris sh -c "printf '%s\n' 'Write \"version=\",\$SYSTEM.Version.GetNumber(),\" namespace=\",\$NAMESPACE,!' 'Write ##class(Fixture.API).ObtenerActa(\"P-001\"),!' 'Halt' | MSYS_NO_PATHCONV=1 docker exec -i ${PREFIJO}iris iris session IRIS -U USER | grep -E 'version=|\"ok\"'"
      echo "       Nota: la terminal entra por el sistema operativo del contenedor, no por el Superserver (1972)"
      echo "       ni con el usuario de la API: no reemplaza la prueba de la Native API."
      ;;
    *) echo "[SKIP] producto desconocido: $p" ;;
  esac
done

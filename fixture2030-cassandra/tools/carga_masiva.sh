#!/usr/bin/env bash
# =====================================================================
# Hito 6 - Fixture 2030 - Carga masiva de comentarios (RF11, RF12)
# =====================================================================
# Genera el dataset sintetico y lo carga en Cassandra con el comando COPY
# de cqlsh, midiendo el tiempo real de cada etapa.
#
# Uso (desde fixture2030-cassandra/):
#   bash tools/carga_masiva.sh              # 1.000.000 de comentarios
#   bash tools/carga_masiva.sh 50000        # carga chica de prueba
#
# Requisitos: el servicio ya levantado (docker compose up -d) y el esquema
# creado (scripts/01-keyspace.cql y scripts/02-tablas.cql).
# =====================================================================
set -euo pipefail

FILAS="${1:-1000000}"
CONTENEDOR="fixture2030-cassandra"
KEYSPACE="fixture2030"
# Paralelismo del COPY: subir INGESTRATE si la notebook lo aguanta.
INGESTRATE="${INGESTRATE:-50000}"
NUMPROCESSES="${NUMPROCESSES:-4}"
CHUNKSIZE="${CHUNKSIZE:-5000}"

cd "$(dirname "$0")/.."

echo "==> 1/3  Generando ${FILAS} comentarios sinteticos en ./data"
t0=$(date +%s)
python3 tools/generar_comentarios.py --filas "${FILAS}" --salida data
t1=$(date +%s)
echo "    Generacion: $((t1 - t0)) s"

copiar() {
  local tabla="$1" columnas="$2" archivo="$3"
  echo "==> Cargando ${tabla} desde ${archivo}"
  docker compose exec -T cassandra cqlsh --request-timeout=3600 -k "${KEYSPACE}" -e "
    COPY ${tabla} (${columnas})
    FROM '/data/${archivo}'
    WITH HEADER = TRUE
     AND INGESTRATE = ${INGESTRATE}
     AND NUMPROCESSES = ${NUMPROCESSES}
     AND CHUNKSIZE = ${CHUNKSIZE}
     AND MAXBATCHSIZE = 20
     AND DATETIMEFORMAT = '%Y-%m-%d %H:%M:%S%z';"
}

echo "==> 2/3  Cargando los CSV con COPY (esto es lo que se cronometra)"
t2=$(date +%s)

copiar comentarios_por_partido \
  "id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en" \
  "comentarios_por_partido.csv"

copiar comentarios_por_usuario \
  "id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en" \
  "comentarios_por_usuario.csv"

copiar comentarios_en_revision \
  "id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en" \
  "comentarios_en_revision.csv"

t3=$(date +%s)
CARGA=$((t3 - t2))
echo "    Carga: ${CARGA} s"

echo "==> 3/3  Resultado"
TOTAL_FILAS=$((FILAS * 2))
if [ "${CARGA}" -gt 0 ]; then
  echo "    Filas escritas (2 tablas principales): ${TOTAL_FILAS}"
  echo "    Tasa observada (extremo a extremo): $((TOTAL_FILAS / CARGA)) escrituras/segundo"
  echo
  echo "    NOTA: este numero incluye el arranque de cqlsh (~3-5 s por tabla)"
  echo "    y el parseo de los CSV. La tasa neta de cada COPY es la que reporta"
  echo "    la linea 'rows imported ... in N seconds' de cada bloque de arriba."
  echo "    Para medir escritura pura contra el modelo usar benchmark_escritura.sh."
else
  echo "    Carga demasiado rapida para medir; repetir con mas filas."
fi
echo
echo "Registrar en docs/evidencia.md: fecha, version de Cassandra, CPU/RAM"
echo "de la notebook, tasa obtenida y parametros INGESTRATE/NUMPROCESSES."
echo "Verificacion del volumen y la distribucion:"
echo "  docker compose exec cassandra cqlsh --request-timeout=600 -f /scripts/06-medicion.cql"

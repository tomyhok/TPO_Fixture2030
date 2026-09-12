#!/usr/bin/env bash
# =====================================================================
# Hito 6 - Fixture 2030 - Prueba de escritura sostenida (RF12)
# =====================================================================
# Usa cassandra-stress, incluido en la imagen oficial, con un perfil propio
# que escribe exactamente sobre comentarios_por_partido (mismo esquema, misma
# clave de particion). No mide una tabla generica: mide NUESTRO modelo.
#
# Uso (desde fixture2030-cassandra/):
#   bash tools/benchmark_escritura.sh                 # 500.000 escrituras
#   bash tools/benchmark_escritura.sh 2000000 64      # n operaciones, m hilos
#
# El objetivo del enunciado es 10.000+ escrituras/s "cuando el hardware lo
# permita". Un nodo unico en una notebook normalmente queda por debajo:
# hay que REGISTRAR la tasa real y explicar el limite, no inventarla.
# =====================================================================
set -euo pipefail

OPERACIONES="${1:-500000}"
HILOS="${2:-32}"
CONTENEDOR="fixture2030-cassandra"

cd "$(dirname "$0")/.."

echo "==> Recursos del contenedor antes de la prueba"
docker stats --no-stream "${CONTENEDOR}" || true
docker compose exec -T cassandra nodetool status

echo
echo "==> cassandra-stress: ${OPERACIONES} escrituras, ${HILOS} hilos"
echo "    perfil: /tools/stress_comentarios.yaml"
# cassandra-stress vive en /opt/cassandra/tools/bin, que no esta en el PATH
# del contenedor oficial.
docker compose exec -T cassandra /opt/cassandra/tools/bin/cassandra-stress \
  user profile=/tools/stress_comentarios.yaml \
       ops\(insert=1\) \
       n="${OPERACIONES}" \
       cl=ONE \
  -rate threads="${HILOS}" \
  -node 127.0.0.1

echo
echo "==> Estado de la tabla despues de la prueba"
docker compose exec -T cassandra nodetool tablestats fixture2030.comentarios_por_partido
docker compose exec -T cassandra nodetool tablehistograms fixture2030 comentarios_por_partido

cat <<'TXT'

---------------------------------------------------------------------
Que anotar en docs/evidencia.md (RNF9 y restriccion de "Rendimiento"):
  * Fecha y hora de la corrida.
  * Version reportada por SHOW VERSION.
  * CPU, RAM y almacenamiento (SSD/HDD) de la notebook, y cuanta RAM
    tiene asignada Docker Desktop.
  * Parametros usados: n, threads, cl.
  * De la salida de cassandra-stress: "Op rate", "Latency mean",
    "Latency 99th percentile" y "Total errors".
  * De nodetool tablestats: "Compacted partition maximum bytes" y
    "Average live cells per slice".
  * Limitaciones observadas: nodo unico, sin replicacion real, heap de 2G,
    cliente y servidor compartiendo la misma CPU.
---------------------------------------------------------------------
TXT

#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Modo clientes nativos
# =====================================================================
# 1) Desde la notebook (mismo origen que la API): drivers de Python que usa la
#    API (pymongo, neo4j, cassandra-driver, redis-py, HTTP v3, Native API de
#    IRIS) y protocolos crudos (Bolt, CQL, RESP), capa por capa.
# 2) Opcional --cli-contenedor: los CLI oficiales (mongosh, cypher-shell,
#    cqlsh, redis-cli, influxdb3, iris session) dentro del contenedor de cada
#    producto. Es una segunda opinión desde OTRO origen: no prueba el camino
#    notebook -> puerto publicado que usa la API.
#
# Las herramientas no instaladas se informan como SKIP, no como producto caído.
# Uso: bash scripts/prueba_clientes_nativos.sh [--cli-contenedor] [--producto iris]
# =====================================================================
set -uo pipefail
DIR="$(dirname "$0")"
cli=0
argumentos=()
for arg in "$@"; do
  if [ "$arg" = "--cli-contenedor" ]; then cli=1; else argumentos+=("$arg"); fi
done

bash "$DIR/evaluar_conectividad.sh" --modo nativo "${argumentos[@]}"
if [ "$cli" = 1 ]; then
  echo
  bash "$DIR/clientes_en_contenedor.sh"
fi

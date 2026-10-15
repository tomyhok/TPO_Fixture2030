#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Ejecutar la colección Postman desde la terminal (Newman)
# =====================================================================
# Reinicia la muestra (sesiones de Redis y actas de IRIS) y corre las 64
# requests de postman/fixture2030_collection.json con sus pruebas.
# Requiere Node.js (npx descarga Newman la primera vez) y la API levantada.
#
# Uso (desde fixture2030-hito-10-api-integrada/):
#   bash scripts/ejecutar_postman.sh               contra la API de la notebook (8000)
#   bash scripts/ejecutar_postman.sh contenedor    contra la API en contenedor (8001)
# =====================================================================
set -euo pipefail
HITO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HITO"
ENTORNO="${1:-local}"

bash scripts/reiniciar_muestra.sh
npx -y newman@6 run postman/fixture2030_collection.json \
  -e "postman/fixture2030_${ENTORNO}.postman_environment.json" --color off

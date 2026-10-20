#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Ejecutar la colección Postman desde la terminal (Newman)
# =====================================================================
# Ejecuta diez lecturas esenciales sin reiniciar ni modificar muestras.
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

npx -y newman@6 run postman/fixture2030_collection.json \
  -e "postman/fixture2030_${ENTORNO}.postman_environment.json" --color off

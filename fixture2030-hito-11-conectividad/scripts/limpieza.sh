#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Limpieza opcional de lo que puede dejar el diagnóstico
# =====================================================================
# * Detiene instancias temporales de la API (8002, 8003) si quedaron activas.
# * Borra en Redis solo las claves del espacio `diag:h11:*` (las crea la sonda
#   de expiración y se autodestruyen en 1,5 s; esto es por si se cortó a mitad).
# * Borra los __pycache__ del diagnóstico.
# NO toca contenedores, volúmenes ni datos de dominio. No es necesaria para
# repetir las pruebas.
#
# Uso: bash scripts/limpieza.sh
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

for puerto in 8002 8003; do detener_puerto "$puerto"; done
echo "instancias temporales de la API (8002, 8003): detenidas si existían"

if [ "$(docker inspect -f '{{.State.Running}}' fixture2030-redis 2> /dev/null)" = "true" ]; then
  borradas="$(docker exec fixture2030-redis sh -c \
    'redis-cli --scan --pattern "diag:h11:*" | while read -r k; do redis-cli UNLINK "$k" > /dev/null; echo "$k"; done | wc -l')"
  echo "claves diag:h11:* borradas en Redis: $borradas"
fi

find "$HITO/scripts" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "__pycache__ del diagnóstico borrados"

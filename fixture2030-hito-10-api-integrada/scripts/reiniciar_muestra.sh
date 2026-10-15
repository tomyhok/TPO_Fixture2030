#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Reiniciar los datos de muestra que cambian al probar la API
# =====================================================================
# Antes de correr la colección Postman (o de repetir la evidencia):
#   * Redis: vuelve a cargar las sesiones S-0001..S-0010 (vencen a los 30 min).
#   * IRIS:  reinicia las actas P-001 (En Juego), P-002 (Programado) y
#            P-003 (Finalizado) con Fixture.API.CargarMuestra().
# No toca MongoDB, Neo4j, Cassandra ni InfluxDB.
#
# Uso (desde fixture2030-hito-10-api-integrada/): bash scripts/reiniciar_muestra.sh
# =====================================================================
set -euo pipefail
docker() { MSYS_NO_PATHCONV=1 command docker "$@"; }

docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli" > /dev/null
echo "Redis: sesiones S-0001..S-0010 recargadas (TTL 1800 s)"

docker exec -i fixture2030-iris iris session IRIS -U USER <<'EOF' | grep '"ok"'
Write ##class(Fixture.API).CargarMuestra(),!
Halt
EOF
echo "IRIS: actas P-001..P-003 reiniciadas"

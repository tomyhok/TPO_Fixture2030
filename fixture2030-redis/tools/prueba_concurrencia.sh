#!/usr/bin/env bash
# =====================================================================
# Hito 7 - Fixture 2030 - Prueba de concurrencia (RF8)
# =====================================================================
# Lanza N clientes redis-cli en paralelo. Cada cliente hace M INCR sobre
# el MISMO contador. Si ninguna actualizacion se pierde, el valor final
# tiene que ser exactamente N * M.
#
# Usa una clave propia (P-999) para no tocar la muestra. La clave se
# crea con SET ... EX 600: INCR no cambia el TTL, asi que vence sola
# a los 10 minutos.
#
# Uso (desde fixture2030-redis/):
#   bash tools/prueba_concurrencia.sh            # 10 clientes x 1000 INCR
#   bash tools/prueba_concurrencia.sh 20 5000
# =====================================================================

CLIENTES=${1:-10}
OPERACIONES=${2:-1000}
CONTENEDOR=fixture2030-redis
CONTADOR=contador:partido:P-999:visitas

echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Clientes en paralelo: $CLIENTES | INCR por cliente: $OPERACIONES"

# --- Inicio: contador en 0 con TTL de 10 minutos ---
docker exec $CONTENEDOR redis-cli SET $CONTADOR 0 EX 600 > /dev/null

# --- Concurrencia: cada cliente manda sus INCR por su propia conexion ---
for c in $(seq 1 $CLIENTES); do
  (
    for i in $(seq 1 $OPERACIONES); do
      echo "INCR $CONTADOR"
    done | docker exec -i $CONTENEDOR redis-cli > /dev/null
  ) &
done
wait

# --- Verificacion ---
ESPERADO=$((CLIENTES * OPERACIONES))
OBTENIDO=$(docker exec $CONTENEDOR redis-cli GET $CONTADOR)
echo "Contador esperado: $ESPERADO | obtenido: $OBTENIDO"
echo "TTL del contador: $(docker exec $CONTENEDOR redis-cli TTL $CONTADOR) s"

if [ "$OBTENIDO" -eq "$ESPERADO" ]; then
  echo "RESULTADO: OK - no se perdio ninguna actualizacion"
else
  echo "RESULTADO: ERROR - se perdieron actualizaciones"
fi

#!/usr/bin/env bash
# =====================================================================
# Hito 7 - Fixture 2030 - Medicion de operaciones principales (RF12)
# =====================================================================
# Metodo: para cada operacion del modulo se arma un archivo con N veces
# el mismo comando y se lo pasa a redis-cli dentro del contenedor. Se
# toma la hora antes y despues (en milisegundos) y se calcula:
#   operaciones por segundo = N / segundos
#   tiempo promedio por operacion = milisegundos / N
# Es un solo cliente mandando los comandos de a uno.
#
# Se usan claves de prueba bench:* con TTL corto, que se borran al final.
#
# Uso (desde fixture2030-redis/):
#   bash tools/medicion.sh            # 20000 comandos por operacion
#   bash tools/medicion.sh 50000
# =====================================================================

N=${1:-20000}
CONTENEDOR=fixture2030-redis

echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S %Z')"
docker exec $CONTENEDOR redis-cli INFO server | grep redis_version
echo "Comandos por operacion: $N (1 cliente, secuencial)"
echo

# --- Preparacion: claves de prueba con TTL de 10 minutos ---
docker exec $CONTENEDOR redis-cli HSET bench:sesion id_sesion "S-BENCH" usuario_id "U-BENCH" rol "fan" estado "activa" paginas_vistas 0 > /dev/null
docker exec $CONTENEDOR redis-cli EXPIRE bench:sesion 600 > /dev/null
docker exec $CONTENEDOR redis-cli SET bench:cache:partido "ficha-P-001" EX 600 > /dev/null
docker exec $CONTENEDOR redis-cli SET bench:contador 0 EX 600 > /dev/null
docker exec $CONTENEDOR redis-cli ZADD bench:encuesta 0 ARG-10 > /dev/null
docker exec $CONTENEDOR redis-cli EXPIRE bench:encuesta 600 > /dev/null

# --- Funcion de medicion: $1 = nombre, $2 = comando ---
medir() {
  docker exec $CONTENEDOR sh -c "
    seq 1 $N | sed 's/.*/$2/' > /tmp/comandos.txt
    INICIO=\$(date +%s%N)
    redis-cli < /tmp/comandos.txt > /dev/null
    FIN=\$(date +%s%N)
    MS=\$(( (FIN - INICIO) / 1000000 ))
    echo \"$1 | $N comandos en \$MS ms | \$(( $N * 1000 / MS )) ops/s\"
  "
}

# --- Operaciones principales del modulo ---
medir "Leer sesion          (HGETALL)    " "HGETALL bench:sesion"
medir "Renovar sesion       (EXPIRE)     " "EXPIRE bench:sesion 600"
medir "Actividad de sesion  (HINCRBY)    " "HINCRBY bench:sesion paginas_vistas 1"
medir "Cache hit de partido (GET)        " "GET bench:cache:partido"
medir "Escritura de cache   (SET ... EX) " "SET bench:cache:partido ficha-P-001 EX 600"
medir "Contador de visitas  (INCR)       " "INCR bench:contador"
medir "Voto en encuesta     (ZINCRBY)    " "ZINCRBY bench:encuesta 1 ARG-10"

# --- Limpieza ---
docker exec $CONTENEDOR redis-cli DEL bench:sesion bench:cache:partido bench:contador bench:encuesta > /dev/null

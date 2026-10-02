#!/usr/bin/env bash
# =====================================================================
# Hito 7 - Fixture 2030 - Generar la evidencia completa (RF13, RNF3)
# =====================================================================
# Ejecuta todos los scripts en el orden del README y guarda la salida
# de cada uno en docs/evidencia/. Reemplaza los .txt anteriores.
#
# Para medir la tasa de hit de cache.redis se toma INFO stats antes y
# despues y se restan los valores.
#
# Uso (desde fixture2030-redis/, con el contenedor levantado):
#   bash tools/generar_evidencia.sh
# =====================================================================

E=docs/evidencia
CONTENEDOR=fixture2030-redis

ahora() { date '+%Y-%m-%d %H:%M:%S %Z'; }
ejecutar() { docker exec -i $CONTENEDOR sh -c "grep -v '^#' /scripts/$1.redis | redis-cli"; }
encabezado() { echo "# Fecha: $(ahora)"; echo "# $1"; }
stat() { docker exec $CONTENEDOR redis-cli INFO stats | grep "^$1:" | cut -d: -f2 | tr -d '\r'; }

# --- 0) Ambiente y punto de partida limpio ---
{ encabezado "docker compose ps"; docker compose ps; } > $E/00_ambiente.txt 2>&1
ejecutar limpieza > /dev/null

# --- 1) Inicializacion, carga y sesiones ---
{ encabezado "Script: scripts/inicializacion.redis"; ejecutar inicializacion; } > $E/01_inicializacion.txt 2>&1
{ encabezado "Script: scripts/carga_muestra.redis"; ejecutar carga_muestra; } > $E/02_carga_muestra.txt 2>&1
{ encabezado "Script: scripts/sesiones.redis"; ejecutar sesiones; } > $E/03_sesiones.txt 2>&1

# --- 2) Expiracion: esperar a que venza sesion:S-0199 (EXPIRE 5) ---
sleep 7
{
  encabezado "Verificacion de expiracion de sesion:S-0199, 7 s despues de crearla con EXPIRE 5"
  echo "> TTL sesion:S-0199";     docker exec $CONTENEDOR redis-cli TTL sesion:S-0199
  echo "> HGETALL sesion:S-0199"; docker exec $CONTENEDOR redis-cli HGETALL sesion:S-0199
  echo "> INFO stats (expired_keys)"; docker exec $CONTENEDOR redis-cli INFO stats | grep expired_keys
} > $E/04_sesiones_expiracion.txt 2>&1

# --- 3) Cache, con hits y misses antes y despues ---
HITS_ANTES=$(stat keyspace_hits); MISSES_ANTES=$(stat keyspace_misses)
{ encabezado "Script: scripts/cache.redis"; ejecutar cache; } > $E/05_cache.txt 2>&1
HITS_DESPUES=$(stat keyspace_hits); MISSES_DESPUES=$(stat keyspace_misses)
{
  encabezado "Hits y misses de cache.redis (INFO stats antes y despues)"
  echo "keyspace_hits   antes=$HITS_ANTES despues=$HITS_DESPUES diferencia=$((HITS_DESPUES - HITS_ANTES))"
  echo "keyspace_misses antes=$MISSES_ANTES despues=$MISSES_DESPUES diferencia=$((MISSES_DESPUES - MISSES_ANTES))"
} > $E/06_tasa_hit.txt 2>&1

# --- 4) Concurrencia ---
{ encabezado "Script: scripts/concurrencia.redis"; ejecutar concurrencia; } > $E/07_concurrencia.txt 2>&1
{ bash tools/prueba_concurrencia.sh 10 1000; echo; bash tools/prueba_concurrencia.sh 20 5000; } > $E/08_prueba_concurrencia.txt 2>&1

# --- 5) Medicion y metricas ---
bash tools/medicion.sh 20000 > $E/09_medicion.txt 2>&1
{ encabezado "Script: scripts/metricas.redis"; ejecutar metricas; } > $E/10_metricas.txt 2>&1

# --- 6) Persistencia: reiniciar el contenedor y comprobar los datos ---
{
  encabezado "Persistencia: claves antes y despues de reiniciar el contenedor"
  echo "> INFO keyspace (antes)"; docker exec $CONTENEDOR redis-cli INFO keyspace
  echo "> docker compose restart redis"; docker compose restart redis 2>&1
  sleep 3
  echo "> INFO keyspace (despues)"; docker exec $CONTENEDOR redis-cli INFO keyspace
  echo "> HGET sesion:S-0005 usuario_id"; docker exec $CONTENEDOR redis-cli HGET sesion:S-0005 usuario_id
  echo "> TTL sesion:S-0005 (el TTL se conserva y sigue corriendo)"; docker exec $CONTENEDOR redis-cli TTL sesion:S-0005
  echo "> ls ~/docker/data/redis"; ls -R ~/docker/data/redis | sed "s|$HOME|~|"
} > $E/11_persistencia.txt 2>&1

# --- 7) Recursos del equipo (RNF10) ---
{
  encabezado "Recursos del equipo"
  echo "Docker: $(docker --version)"
  echo "Imagen: $(docker image inspect redis:latest --format '{{index .RepoDigests 0}}')"
  echo "CPUs y memoria asignadas a Docker: $(docker info --format '{{.NCPU}} CPU, {{.MemTotal}} bytes')"
  uname -sm
} > $E/12_recursos.txt 2>&1

echo "Evidencia generada en $E/"
ls $E

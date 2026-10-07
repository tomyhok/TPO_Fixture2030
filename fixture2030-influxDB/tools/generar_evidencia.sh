#!/usr/bin/env bash
# =====================================================================
# Hito 8 - Fixture 2030 - Generar la evidencia completa (RF13, RF14, RNF10)
# =====================================================================
# Ejecuta los scripts en el orden del README y guarda la salida de cada
# uno en docs/evidencia/. Reemplaza los .txt anteriores.
#
# Uso (desde fixture2030-influxDB/, con el contenedor levantado):
#   bash tools/generar_evidencia.sh [cantidad_de_puntos]   (default 1000000)
# =====================================================================

PUNTOS=${1:-1000000}
E=docs/evidencia
CONTENEDOR=fixture2030-influxdb

cd "$(dirname "$0")/.."

ahora() { date '+%Y-%m-%d %H:%M:%S %Z'; }
encabezado() { echo "# Fecha: $(ahora)"; echo "# $1"; }
# Mide la duración de un comando en segundos (con decimales).
medir() { local t0 t1; t0=$(python3 -c 'import time;print(time.time())'); "$@"; t1=$(python3 -c 'import time;print(time.time())'); python3 -c "print(f'Duración: {$t1 - $t0:.2f} s')"; }

# --- 0) Ambiente: versión, contenedor y recursos del equipo ---
{
  encabezado "Ambiente"
  echo "> docker exec $CONTENEDOR influxdb3 --version"; docker exec $CONTENEDOR influxdb3 --version
  echo "> docker image inspect (imagen usada)"; docker inspect $CONTENEDOR --format '{{.Config.Image}} {{.Image}}'
  echo "> docker compose ps"; docker compose ps
  echo "> Recursos del host"; uname -srm
  if command -v sysctl > /dev/null && sysctl -n hw.ncpu > /dev/null 2>&1; then
    echo "CPU: $(sysctl -n machdep.cpu.brand_string 2>/dev/null) ($(sysctl -n hw.ncpu) núcleos)"
    echo "RAM: $(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 )) GB"
  else
    echo "CPU: $(nproc) núcleos"; free -h | head -2
  fi
  echo "> Recursos asignados a Docker"; docker info --format 'CPUs: {{.NCPU}}  RAM: {{.MemTotal}} bytes'
} > $E/00_ambiente.txt 2>&1

# --- 1) Inicialización (token fuera del repo + base con retención) ---
{ encabezado "Script: scripts/inicializacion.sh"; bash scripts/inicializacion.sh | grep -v apiv3_; } > $E/01_inicializacion.txt 2>&1

# --- 2) Generación de puntos (separada de la carga) ---
rm -f data_estadisticas.lp
{
  encabezado "Script: python3 scripts/generacion_puntos.py $PUNTOS data_estadisticas.lp"
  medir python3 scripts/generacion_puntos.py "$PUNTOS" data_estadisticas.lp | tr '\r' '\n' | grep -v Progreso
  echo "> Tamaño del archivo"; ls -lh data_estadisticas.lp | awk '{print $5, $9}'
  echo "> Primeras 3 líneas (line protocol, precisión en segundos)"; head -3 data_estadisticas.lp
} > $E/02_generacion.txt 2>&1

# --- 3) Carga por lotes ---
{ encabezado "Script: scripts/carga_lotes.sh"; medir bash scripts/carga_lotes.sh; } > $E/03_carga.txt 2>&1

# --- 4) Consultas, agregaciones y validación ---
{ encabezado "Script: scripts/consultas_temporales.sh"; medir bash scripts/consultas_temporales.sh; } > $E/04_consultas_temporales.txt 2>&1
{ encabezado "Script: scripts/agregaciones.sh"; medir bash scripts/agregaciones.sh; } > $E/05_agregaciones.txt 2>&1
{ encabezado "Script: scripts/validacion.sh"; medir bash scripts/validacion.sh; } > $E/06_validacion.txt 2>&1

# --- 5) Persistencia: reiniciar el contenedor y volver a contar ---
{
  encabezado "Persistencia: docker restart $CONTENEDOR y nueva validación"
  docker restart $CONTENEDOR
  sleep 5
  bash scripts/validacion.sh
  echo "> Datos en el host (~/docker/data/influxdb)"; du -sh ~/docker/data/influxdb | sed "s#$HOME#~#"
} > $E/07_persistencia.txt 2>&1

echo "Evidencia generada en $E/"

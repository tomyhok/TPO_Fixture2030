#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Evaluación de conectividad (punto de entrada)
# =====================================================================
# Uso (desde cualquier carpeta):
#   bash scripts/evaluar_conectividad.sh                    modo completo
#   bash scripts/evaluar_conectividad.sh --tcp-only         configuración + DNS + TCP (sin drivers)
#   bash scripts/evaluar_conectividad.sh --native-only      + clientes nativos y sondas
#   bash scripts/evaluar_conectividad.sh --api-only         rutas de la API del Hito 10
#   bash scripts/evaluar_conectividad.sh --modo nativo --producto redis,iris
#   bash scripts/evaluar_conectividad.sh --help             todas las opciones
#
# La configuración se toma del .env del Hito 10, de config/conectividad.env
# (opcional) y de variables de entorno, que tienen prioridad:
#   MONGO_HOST=mongodb bash scripts/evaluar_conectividad.sh --tcp-only
#
# No crea, modifica ni borra datos. No imprime secretos.
# SKIP = prueba no ejecutada (falta herramienta/configuración o falló una capa
# previa); no significa "producto caído".
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

argumentos=()
for arg in "$@"; do
  case "$arg" in
    --tcp-only) argumentos+=(--modo tcp) ;;
    --native-only) argumentos+=(--modo nativo) ;;
    --api-only) argumentos+=(--modo api) ;;
    --config-only) argumentos+=(--modo config) ;;
    *) argumentos+=("$arg") ;;
  esac
done

if ! "$PY" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2> /dev/null; then
  echo "Se necesita Python 3.11+ (definir PYTHON=/ruta/a/python). Intérprete actual: $PY" >&2
  exit 2
fi
evaluar "${argumentos[@]}"

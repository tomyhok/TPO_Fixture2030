#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Ejecutar las pruebas
# =====================================================================
#   bash scripts/ejecutar_pruebas.sh          unitarias + integración
#   bash scripts/ejecutar_pruebas.sh unit     solo unitarias (sin bases)
#
# Las unitarias usan dobles en memoria y no necesitan Docker. Las de
# integración usan la API real contra las seis fuentes: antes se verifica
# la conectividad y, si falta alguna, se informa cuál y se detiene.
# Ninguna prueba imprime ni registra credenciales.
# =====================================================================
set -uo pipefail
HITO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HITO"
PY=".venv/Scripts/python"; [ -x "$PY" ] || PY=".venv/bin/python"

echo "=== Pruebas unitarias ==="
"$PY" -m pytest tests/unit -q || exit 1
[ "${1:-todo}" = "unit" ] && exit 0

echo
echo "=== Conectividad ==="
"$PY" scripts/verificar_conectividad.py || {
  echo "Hay fuentes sin conexión: levantar los contenedores y ejecutar scripts/preparar_datos.sh"; exit 1; }

echo
echo "=== Pruebas de integración ==="
"$PY" -m pytest tests/integration -v

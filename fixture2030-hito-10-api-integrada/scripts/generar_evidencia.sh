#!/usr/bin/env bash
# Seis lecturas por HTTP; no reinicia datos ni detiene motores.
set -euo pipefail
HITO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HITO"
PY=".venv/Scripts/python"; [ -x "$PY" ] || PY=".venv/bin/python"
exec "$PY" scripts/generar_evidencia.py

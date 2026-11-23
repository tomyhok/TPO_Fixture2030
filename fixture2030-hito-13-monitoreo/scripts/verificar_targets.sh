#!/usr/bin/env bash
# =====================================================================
# Hito 13 - Verificar targets y reglas en Prometheus
# =====================================================================
set -euo pipefail

DIR_HITO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_HITO"

PYTHON_BIN="${PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" scripts/verificar_targets.py --guardar "$@"

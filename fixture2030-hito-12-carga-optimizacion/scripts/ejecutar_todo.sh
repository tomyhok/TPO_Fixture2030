#!/usr/bin/env bash
# Hito 12 - Secuencia completa: capacidad (sin pausa) y carga fija (500 ops/s),
# cada una en linea base y optimizado. Tarda ~25 minutos.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/ejecutar_linea_base.sh
bash scripts/ejecutar_prueba_optimizada.sh
bash scripts/ejecutar_linea_base.sh --tasa 10
bash scripts/ejecutar_prueba_optimizada.sh --tasa 10

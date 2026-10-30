#!/usr/bin/env bash
# Hito 12 - Prueba de la hipotesis "el generador limita la linea base":
# repite la linea base de capacidad con 3 procesos (variabilidad) y con 6.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/ejecutar_linea_base.sh --procesos 3
bash scripts/ejecutar_linea_base.sh --procesos 6

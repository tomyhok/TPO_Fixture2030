#!/usr/bin/env bash
# Hito 12 - Linea base: muro leido directo de Cassandra + validacion de integridad.
# Los argumentos extra pasan a ejecutar_carga.py (ej: --tasa 10 --usuarios 50).
set -euo pipefail
cd "$(dirname "$0")/.."
sleep 60  # separa las ventanas de 1 minuto de una corrida anterior
python scripts/ejecutar_carga.py --modo base "$@"
python scripts/validar_integridad.py "$(ls -t docs/evidencia/resultados/base_*[0-9].json | head -1)"

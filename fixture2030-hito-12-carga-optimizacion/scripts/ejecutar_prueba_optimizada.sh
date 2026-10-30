#!/usr/bin/env bash
# Hito 12 - Prueba optimizada: muro en Redis. Mismos argumentos que la linea base.
set -euo pipefail
cd "$(dirname "$0")/.."
sleep 60  # separa las ventanas de 1 minuto de una corrida anterior
python scripts/ejecutar_carga.py --modo optimizado "$@"
python scripts/validar_integridad.py "$(ls -t docs/evidencia/resultados/optimizado_*[0-9].json | head -1)"

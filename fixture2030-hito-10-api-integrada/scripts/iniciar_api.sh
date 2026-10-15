#!/usr/bin/env bash
# =====================================================================
# Hito 10 - Iniciar la API REST integrada
# =====================================================================
# Crea el entorno virtual si no existe, instala dependencias y levanta
# uvicorn con el host y puerto del .env. Los logs se ven en consola y se
# guardan en logs/api.log (excluido del repositorio).
#
# Uso (desde fixture2030-hito-10-api-integrada/): bash scripts/iniciar_api.sh
# Detener: Ctrl+C (no afecta a los contenedores ni a sus datos).
# =====================================================================
set -euo pipefail
HITO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HITO"

[ -f .env ] || { echo "Falta .env: copiar .env.example a .env y completar las contraseñas."; exit 1; }

if [ ! -d .venv ]; then
  echo "Creando entorno virtual con Python 3.12..."
  if command -v py > /dev/null; then py -3.12 -m venv .venv; else python3.12 -m venv .venv; fi
fi
PY=".venv/Scripts/python"; [ -x "$PY" ] || PY=".venv/bin/python"
"$PY" -m pip install -q -r requirements.txt

HOST="$(grep -E '^API_HOST=' .env | cut -d= -f2 | tr -d '\r')"; HOST="${HOST:-127.0.0.1}"
PORT="$(grep -E '^API_PORT=' .env | cut -d= -f2 | tr -d '\r')"; PORT="${PORT:-8000}"

mkdir -p logs
echo "API en http://$HOST:$PORT  ·  Swagger UI: http://$HOST:$PORT/docs"
"$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --no-access-log 2>&1 | tee -a logs/api.log

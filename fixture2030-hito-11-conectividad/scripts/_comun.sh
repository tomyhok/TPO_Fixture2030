#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Funciones comunes de los scripts (se incluye con `source`)
# =====================================================================
# * Ubica el intérprete de Python con los drivers (por defecto el entorno
#   virtual de la API del Hito 10, para usar exactamente los mismos drivers).
# * Lee variables del .env sin ejecutarlo y sin imprimir su valor.
# * Detiene procesos por puerto (en Windows el venv lanza dos procesos).
# =====================================================================

HITO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAIZ="$(cd "$HITO/.." && pwd)"
HITO10="$RAIZ/fixture2030-hito-10-api-integrada"
EVIDENCIA="$HITO/docs/evidencia"

if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"
elif [ -x "$HITO10/.venv/Scripts/python" ]; then PY="$HITO10/.venv/Scripts/python"
elif [ -x "$HITO10/.venv/bin/python" ]; then PY="$HITO10/.venv/bin/python"
elif [ -x "$HITO/.venv/Scripts/python" ]; then PY="$HITO/.venv/Scripts/python"
elif [ -x "$HITO/.venv/bin/python" ]; then PY="$HITO/.venv/bin/python"
else PY="$(command -v python3 || command -v python || echo python)"
fi

# Git Bash convierte /rutas al pasarlas a docker: se desactiva solo en docker.
docker() { MSYS_NO_PATHCONV=1 command docker "$@"; }
ruta_host() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

# Lee una variable de los archivos de configuración (Hito 11 local > .env del Hito 10).
leer_env() {
  local valor=""
  for archivo in "$HITO/config/conectividad.env" "$HITO10/.env"; do
    if [ -f "$archivo" ] && grep -qE "^$1=" "$archivo"; then
      valor="$(grep -E "^$1=" "$archivo" | head -1 | cut -d= -f2- | tr -d '\r')"
      break
    fi
  done
  printf '%s' "${!1:-$valor}"
}

evaluar() { "$PY" "$HITO/scripts/evaluar_conectividad.py" "$@"; }

marca() { date -u +%Y-%m-%dT%H:%M:%SZ; }
titulo() { echo; echo "=================================================================="; echo "## $*"; echo "## $(marca)"; echo "=================================================================="; }

# GET a la API con request ID propio: imprime status, duración y cuerpo (sin headers sensibles).
api_get() {
  local base="$1" path="$2" rid="$3"
  echo "\$ curl -H 'X-Request-ID: $rid' $base$path"
  curl -s -m "${API_TIMEOUT_S:-15}" -H "X-Request-ID: $rid" -w '\n-> HTTP %{http_code} en %{time_total} s\n' "$base$path" \
    || echo "-> sin respuesta (API no alcanzable)"
}

# Detiene el proceso que escucha en un puerto local (uvicorn temporal).
detener_puerto() {
  local puerto="$1" pid
  if command -v netstat > /dev/null && command -v taskkill > /dev/null; then
    for pid in $(netstat -ano | grep -E "127\.0\.0\.1:$puerto .*LISTENING" | awk '{print $NF}' | sort -u); do
      taskkill //PID "$pid" //T //F > /dev/null 2>&1 || true
    done
  elif command -v fuser > /dev/null; then
    fuser -k "$puerto/tcp" > /dev/null 2>&1 || true
  fi
}

# Espera a que una URL responda 200 (máximo $2 segundos).
esperar_url() {
  local url="$1" maximo="${2:-30}" i
  for ((i = 0; i < maximo; i++)); do
    [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$url")" = "200" ] && return 0
    sleep 1
  done
  return 1
}

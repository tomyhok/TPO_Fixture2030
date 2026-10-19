#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Modo API: rutas GET del Hito 10 con X-Request-ID propio
# =====================================================================
# Distingue: API no alcanzable, dependencia fallida (503/504), recurso
# inexistente (404), respuesta vacía válida (200 con lista vacía), error de
# validación (400) y operación exitosa. Busca cada request ID en el log de la
# API (API_LOG_FILE, por defecto el logs/api.log del Hito 10).
#
# Requisito: la API iniciada (bash ../fixture2030-hito-10-api-integrada/scripts/iniciar_api.sh)
# Uso: bash scripts/prueba_api.sh [--producto neo4j] ; API_URL=http://127.0.0.1:8001 bash scripts/prueba_api.sh
# =====================================================================
set -uo pipefail
exec bash "$(dirname "$0")/evaluar_conectividad.sh" --modo api "$@"

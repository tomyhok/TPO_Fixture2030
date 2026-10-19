#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Modo puertos: configuración + resolución + TCP (+ estado del contenedor)
# =====================================================================
# Solo usa la biblioteca estándar de Python: funciona sin ningún driver.
# Un TCP OK solo prueba que hay un listener: no prueba protocolo, credenciales
# ni contexto. Por eso la matriz deja el producto en "desconocido".
#
# Uso: bash scripts/prueba_tcp.sh [--producto mongodb,redis] [--json salida.json]
# =====================================================================
set -uo pipefail
exec bash "$(dirname "$0")/evaluar_conectividad.sh" --modo tcp "$@"

#!/usr/bin/env bash
# =====================================================================
# Hito 11 - Genera toda la evidencia de docs/evidencia/ en una corrida
# =====================================================================
# Orden: entorno y topología -> TCP -> clientes nativos -> CLI en contenedor
# -> diagnóstico desde la red Docker -> API -> matriz completa -> fallo
# controlado (MongoDB detenido y recuperado) -> escenarios de configuración
# -> logs de la API -> verificación de secretos.
#
# Toda salida pasa por scripts/redactar.py antes de escribirse (RNF8).
# Ninguna prueba borra datos ni volúmenes. El fallo controlado detiene y
# vuelve a iniciar fixture2030-mongodb (docker stop/start).
#
# Requisitos: bases levantadas, datos preparados (Hito 10) y la API iniciada.
# Uso: bash scripts/generar_evidencia.sh
# =====================================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

API_URL="${API_URL:-http://127.0.0.1:8000}"
INICIO="$(marca)"
COMMIT="$(git -C "$RAIZ" rev-parse --short HEAD 2> /dev/null || echo '?')"
mkdir -p "$EVIDENCIA/capturas_redactadas"

redactar() { "$PY" "$HITO/scripts/redactar.py"; }
guardar() {  # archivo, descripción, comando...
  local archivo="$1" descripcion="$2"; shift 2
  echo ">> $archivo"
  {
    echo "# $descripcion"
    echo "# Generado: $(marca) con scripts/generar_evidencia.sh (commit $COMMIT, origen: notebook)"
    echo
    "$@" 2>&1
  } | redactar > "$EVIDENCIA/$archivo"
}

esperar_url "$API_URL/health/live" 10 || { echo "La API no responde en $API_URL: iniciarla antes."; exit 1; }

entorno() {
  titulo "Versiones"
  echo "docker server $(docker version --format '{{.Server.Version}}' 2> /dev/null)"
  echo "python $("$PY" -c 'import platform; print(platform.python_version())') (entorno virtual del Hito 10)"
  curl -s "$API_URL/health/live"; echo "  <- API $API_URL"
  titulo "Contenedores y puertos publicados (host:puerto -> puerto interno)"
  docker ps -a --filter "name=fixture2030-" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
  titulo "Red de Docker Compose: nombre de servicio -> IP interna"
  local red
  red="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' fixture2030-mongodb | awk '{print $1}')"
  echo "red: $red"
  docker network inspect "$red" -f '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}' | sort
  titulo "Volúmenes (persistencia que ninguna prueba borra)"
  for c in mongodb neo4j cassandra redis influxdb iris; do
    docker inspect -f "{{.Name}}: {{range .Mounts}}{{if or (eq .Type \"volume\") (eq .Destination \"/var/lib/cassandra\") (eq .Destination \"/data\") (eq .Destination \"/durable\") (eq .Destination \"/var/lib/influxdb3/data\")}}{{.Type}}:{{if .Name}}{{.Name}}{{else}}~/docker/data{{end}}->{{.Destination}} {{end}}{{end}}" "fixture2030-$c"
  done
}

guardar 00_entorno_y_topologia.txt "Entorno, contenedores, red y volúmenes" entorno
guardar resultados_tcp.txt "Modo TCP: configuración + resolución + TCP (+ estado del contenedor)" \
  evaluar --modo tcp --etiqueta "modo tcp" --json "$EVIDENCIA/resultados_tcp.json"
guardar resultados_clientes.txt "Modo nativo: protocolo, identidad, contexto, lectura y sondas (con sonda de expiración de Redis)" \
  env REDIS_SONDA_EXPIRACION=1 "$PY" "$HITO/scripts/evaluar_conectividad.py" --modo nativo --etiqueta "modo nativo" \
  --json "$EVIDENCIA/resultados_clientes.json"
guardar resultados_clientes_contenedor.txt "CLI oficiales dentro del contenedor de cada producto (otro origen)" \
  bash "$HITO/scripts/clientes_en_contenedor.sh"
guardar resultados_red_docker.txt "Diagnóstico ejecutado dentro de la red de Docker Compose" \
  bash "$HITO/scripts/evaluar_desde_red_docker.sh"
guardar resultados_api.txt "Modo API: rutas del Hito 10 con request ID y log asociado" \
  evaluar --modo api --etiqueta "modo api" --json "$EVIDENCIA/resultados_api.json"
guardar resultados_completo.txt "Modo completo (matriz de conectividad)" \
  evaluar --modo completo --etiqueta "modo completo" --json "$EVIDENCIA/resultados_completo.json" \
  --markdown "$EVIDENCIA/matriz_completa.md"
guardar fallo_controlado_mongodb.txt "Fallo controlado: MongoDB detenido y recuperado (RF20, RF21)" \
  bash "$HITO/scripts/fallo_controlado.sh"
guardar escenarios_configuracion.txt "Configuración incorrecta y corrección; API con configuración errónea (RF17, RF20)" \
  bash "$HITO/scripts/escenarios_configuracion.sh"
guardar logs_api_h11.txt "Líneas del log de la API con request ID del Hito 11 (desde $INICIO)" \
  awk -v desde="$INICIO" '$1 >= desde && /request_id=h11-/' "$HITO10/logs/api.log"

# El JSON y el Markdown los escribe el diagnóstico ya redactado; se repasa igual.
for f in "$EVIDENCIA"/*.json "$EVIDENCIA"/*.md; do
  [ -f "$f" ] && [ "$(basename "$f")" != "README.md" ] && { redactar < "$f" > "$f.tmp" && mv "$f.tmp" "$f"; }
done
guardar verificacion_secretos.txt "Búsqueda de los valores secretos configurados en toda la evidencia" \
  "$PY" "$HITO/scripts/redactar.py" --verificar "$EVIDENCIA"

echo
echo "Evidencia generada en $EVIDENCIA (inicio $INICIO, fin $(marca))"

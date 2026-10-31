# Métricas, Configuración de Prometheus y Consultas PromQL (Hito 13)

Este documento desarrolla la **Sección 5.2 (Prometheus)** y cumple los requisitos **RF1, RF2, RF3, RF4, RF8, RNF3 y RNF4** de la consigna del Hito 13.

---

## 1. Configuración de Prometheus (`prometheus.yml`)

El archivo [`../prometheus.yml`](../prometheus.yml) se basa en la plantilla entregada por la cátedra e incorpora el job de la API integrada y el archivo de reglas de alerta:

- **Intervalo de scraping (`scrape_interval`):** `15s` (frecuencia con la que Prometheus hace *pull* HTTP sobre cada target).
- **Intervalo de evaluación (`evaluation_interval`):** `15s` (frecuencia con la que Prometheus evalúa las reglas de [`../prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml)).
- **Retención:** Por defecto de Prometheus TSDB (`15d` en `/prometheus`, persistido en `${HOME}/docker/data/prometheus`).

### Relación entre cada `job_name` y el componente observado

| Job (`job_name`) | Target (`instance`) | Endpoint | Etiquetas (`labels`) | Componente observado |
|---|---|---|---|---|
| `prometheus` | `prometheus:9090` | `/metrics` | `componente="prometheus-tsdb"`, `capa="monitoreo"` | Servidor Prometheus (auto-monitoreo del recolector TSDB). |
| `node-exporter` | `node-exporter:9100` | `/metrics` | `componente="host-docker"`, `capa="infraestructura"` | Recursos de infraestructura del nodo (CPU, RAM, disco, red). |
| `fixture-api` | `host.docker.internal:8000` | `/metrics` | `componente="api-integrada"`, `capa="aplicacion"` | API REST integrada del Hito 10 y estado/operaciones de sus 6 adaptadores NoSQL (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`). |

---

## 2. Diferenciación entre Métricas de Aplicación e Infraestructura (RF4)

Tal como se estudia en la **Clase 14**, separar las métricas de infraestructura de las de aplicación permite responder en segundos la pregunta de la FIFA: *«¿Cómo distinguen que el problema está en la API, en una base o en el servidor?»*

| Categoría | Fuente | Ejemplos de Métricas | Tipo Prometheus | Qué Diagnostica |
|---|---|---|---|---|
| **Infraestructura** | `node-exporter:9100` | `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_filesystem_avail_bytes` | Counter / Gauge | Saturación física o de la VM de contenedores (CPU al 100%, falta de RAM o disco lleno). |
| **Aplicación (Capa HTTP)** | `fixture-api:8000/metrics` | `fixture_api_http_requests_total`, `fixture_api_http_errors_total`, `fixture_api_http_request_duration_seconds`, `fixture_api_in_flight_requests` | Counter / Histogram / Gauge | Volumen de tráfico de usuarios por endpoint, errores de validación (`400`), recursos ausentes (`404`) y cumplimiento del SLA de latencia (`< 100ms`). |
| **Subsistemas NoSQL (Adaptadores + Salud)** | `fixture-api:8000/metrics` | `fixture_db_up`, `fixture_db_status_info`, `fixture_db_ping_latency_seconds`, `fixture_db_operations_total`, `fixture_db_operation_duration_seconds` | Gauge / Counter / Histogram | Disponibilidad individual de cada una de las 6 bases (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`), tiempo neto de consulta al driver y fallas de dependencia (`503`/`504`). |

---

## 3. Procedimientos Operativos para Targets `UP` y `DOWN` (Sección 5.2)

### 3.1. Procedimiento para validar que un target está `UP`

1. **Vía interfaz web de Prometheus:** Abrir `http://localhost:9090/targets` y verificar que los tres endpoints (`prometheus`, `node-exporter`, `fixture-api`) muestren estado **`UP`** en verde y `Last Scrape < 15s`.
2. **Vía consulta PromQL:** Ejecutar en `http://localhost:9090/graph` la expresión `up`: debe devolver `1` para las tres series.
3. **Vía script automatizado reproducible:**
   ```bash
   python scripts/verificar_targets.py --guardar
   ```
   El script consulta `/api/v1/targets`, verifica que todos los targets tengan `"health": "up"` y devuelve código de salida `0`.

### 3.2. Procedimiento para investigar un target `DOWN` (`up == 0` o `fixture_db_up == 0`)

Cuando Prometheus reporta `up == 0` o `fixture_db_up{db="X"} == 0`, se aplica la metodología de diagnóstico por capas desarrollada en el **Hito 11**:

1. **Caso A — `up{job="fixture-api"} == 0` (Target de la API caído en Prometheus):**
   - Revisar el campo `lastError` en `http://localhost:9090/targets`:
     - Si dice `connection refused`: el proceso Uvicorn de la API en el puerto `8000` del host no está iniciado o escucha solo en `127.0.0.1` bloqueando a `host.docker.internal`. Solución: iniciar la API con `--host 0.0.0.0 --port 8000` y verificar `curl http://localhost:8000/metrics`.
     - Si dice `context deadline exceeded`: el endpoint `/metrics` tardó más que el `scrape_timeout`. Verificar si algún chequeo de salud está demorando y revisar `HEALTH_CACHE_TTL_S`.
2. **Caso B — `fixture_db_up{db="<motor>"} == 0` (Uno de los 6 motores NoSQL reportado como `DOWN`):**
   - Consultar la métrica `fixture_db_status_info{db="<motor>"}` o el endpoint `GET http://localhost:8000/health/dependencias?refrescar=true`:
     - Si `state="not_configured"`: falta una variable de entorno o el archivo `.influxdb3-token`.
     - Si `state="down"`: ejecutar el evaluador por capas del Hito 11 para ese producto específico:
       ```bash
       cd ../fixture2030-hito-11-conectividad
       bash scripts/evaluar_conectividad.sh --producto <motor>
       ```
       Esto determina inmediatamente si falló la capa **TCP** (contenedor detenido → `docker compose up -d <motor>`), **Autenticación** (credencial en `.env`) o **Contexto** (keyspace/base/clase no inicializada).

---

## 4. Consultas PromQL Definidas y Explicadas (RF8)

Se definen **6 consultas PromQL** vinculadas directamente con la arquitectura del Fixture 2030 (superando el mínimo de 2 exigido por **RF8**):

### Consulta 1 — Disponibilidad de los 6 motores NoSQL
```promql
fixture_db_up
```
- **Qué mide:** Estado operativo actual de cada base de datos (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`) según el diagnóstico de la API integrada.
- **Unidad:** Adimensional binaria (`1` = disponible `up`/`degraded`, `0` = no disponible `down`/`not_configured`/`unknown`).
- **Período utilizado:** Valor instantáneo (actualizado en cada scrape cada `15s`, con caché de salud de `10s`).
- **Uso en defensa:** Permite mostrar en vivo cómo al detener un contenedor (`docker stop fixture2030-redis`) únicamente esa serie cae a `0` mientras las otras 5 permanecen en `1`.

### Consulta 2 — Percentil 95 de latencia HTTP por ruta frente al SLA (< 100ms)
```promql
histogram_quantile(0.95, sum by (le, route) (rate(fixture_api_http_request_duration_seconds_bucket[1m])))
```
- **Qué mide:** El tiempo de respuesta debajo del cual se resuelve el 95% de las solicitudes HTTP de cada endpoint de negocio del Fixture (`p95`).
- **Unidad:** Segundos (`s`). El objetivo del TPO (`< 100ms`) equivale a `< 0.1s`.
- **Período utilizado:** Ventana móvil de `1m` (`[1m]`), que abarca 4 intervalos de scraping de `15s` para reaccionar rápidamente durante las pruebas de laboratorio.
- **Uso en defensa:** Verifica empíricamente el cumplimiento del requisito no funcional de latencia `< 100ms` por flujo.

### Consulta 3 — Volumen de operaciones HTTP (Throughput RPS) por ruta y estado
```promql
sum by (route, status) (rate(fixture_api_http_requests_total[1m]))
```
- **Qué mide:** Cantidad promedio de requests HTTP por segundo que procesa cada ruta de la API, separando respuestas exitosas (`200`) de rechazos de validación (`400`), recursos ausentes (`404`) o fallas de base (`503`/`504`).
- **Unidad:** Solicitudes por segundo (`req/s` o `ops/s`).
- **Período utilizado:** Ventana de `1m` (`[1m]`).
- **Uso en defensa:** Muestra el volumen de tráfico absorbido por cada subsistema y cómo se distribuyen las consultas durante la demostración.

### Consulta 4 — Latencia promedio de operación por motor NoSQL (Comparación entre bases, RF7)
```promql
sum by (db, operation) (rate(fixture_db_operation_duration_seconds_sum[1m]))
/
clamp_min(sum by (db, operation) (rate(fixture_db_operation_duration_seconds_count[1m])), 1e-9)
```
- **Qué mide:** El tiempo neto promedio que tarda cada adaptador en ejecutar su consulta nativa contra su motor NoSQL (excluyendo la serialización HTTP de FastAPI).
- **Unidad:** Segundos (`s`).
- **Período utilizado:** Ventana de `1m` (`[1m]`).
- **Uso en defensa:** Permite comparar en un mismo gráfico por qué **Redis** responde en el orden de `~1 ms` (memoria clave-valor), **MongoDB/Neo4j/IRIS** en `~3–10 ms` (documento/grafo/objeto indexado) y **Cassandra/InfluxDB** en `~15–80 ms` (lectura de múltiples particiones o agregación temporal).

### Consulta 5 — Tasa de errores de dependencia por segundo
```promql
sum by (route, codigo) (rate(fixture_api_http_errors_total{codigo=~"DEPENDENCIA_NO_DISPONIBLE|DEPENDENCIA_TIMEOUT"}[1m]))
```
- **Qué mide:** Velocidad a la que se producen fallos de disponibilidad (`503`) o expiración de tiempo (`504`) al consultar las bases de datos, filtrando fuera los errores normales del cliente (`400`/`404`).
- **Unidad:** Errores por segundo (`err/s`).
- **Período utilizado:** Ventana de `1m` (`[1m]`).
- **Uso en defensa:** Distingue un error del usuario (ej. pedir un código ISO inválido `arg`) de una caída real de infraestructura en una base de datos.

### Consulta 6 — Utilización de CPU del nodo de contenedores (Infraestructura)
```promql
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))
```
- **Qué mide:** Fracción de tiempo de CPU ocupado en el host donde corren los contenedores Docker, recolectada por `node-exporter`.
- **Unidad:** Proporción de `0` a `1` (representada en Grafana como porcentaje `0% – 100%` con unidad `percentunit`).
- **Período utilizado:** Ventana de `1m` (`[1m]`).
- **Uso en defensa:** Permite correlacionar si un aumento de latencia en Cassandra o en la API coincide con saturación de CPU del nodo (como se observó en la prueba de carga del Hito 12).

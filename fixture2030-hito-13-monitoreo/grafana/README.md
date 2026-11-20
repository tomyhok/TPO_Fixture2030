# Configuración y Provisioning de Grafana — Fixture 2030 (Hito 13)

Este directorio contiene la configuración reproducible de **Grafana** que se monta automáticamente al iniciar el contenedor `fixture2030-grafana` definido en [`../docker-compose.yml`](../docker-compose.yml).

## 1. Acceso local en laboratorio

- **URL:** `http://localhost:3000`
- **Usuario de laboratorio:** `admin`
- **Contraseña:** se lee de `GRAFANA_ADMIN_PASSWORD` en `../.env`, que no se versiona (RNF6). `scripts/iniciar_monitoreo.*` crea ese archivo con un valor aleatorio si no existe; ver [`../.env.example`](../.env.example).

## 2. Estructura de Provisioning

Grafana se aprovisiona sin intervención manual mediante dos archivos:

1. [`provisioning/datasources/prometheus.yml`](provisioning/datasources/prometheus.yml):
   Registra automáticamente la fuente de datos **Prometheus** (`uid: prometheus`) apuntando a `http://prometheus:9090` dentro de la red del Compose `dash`, con intervalo de scrape de `15s`.
2. [`provisioning/dashboards/dashboards.yml`](provisioning/dashboards/dashboards.yml):
   Crea la carpeta `Fixture Mundial 2030` y carga automáticamente todos los archivos `.json` ubicados en [`dashboards/`](dashboards/).

## 3. Dashboard incluido: `fixture2030_war_room.json`

El tablero **Fixture Mundial 2030 — Observabilidad y Monitoreo NoSQL (Hito 13)** (`uid: fixture2030-war-room`) cumple los requisitos **RF5, RF6, RF7, RNF4** y la **Sección 5.3** de la consigna:

| Fila / Panel | Métricas / Consultas PromQL | Qué permite diagnosticar |
|---|---|---|
| **1. Targets Prometheus (`up`)** | `up` | Verifica que `prometheus`, `node-exporter` y `fixture-api` respondan al scraping cada 15s (`1 = UP`, `0 = DOWN`). |
| **2. Estado de Salud por Motor NoSQL** | `fixture_db_up` | Muestra en vivo qué motores (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`) están operativos (`1`) o caídos (`0`). |
| **3. Latencia HTTP API vs SLA (< 100ms)** | `histogram_quantile(0.95, ...)` y promedio por `route` | Evalúa si las rutas de negocio cumplen el objetivo de latencia `< 100ms` (`0.1s`) del TPO. Incluye umbral visual naranja (`50ms`) y rojo (`100ms`). |
| **4. Volumen de Operaciones (Throughput RPS)** | `sum by (route, status) (rate(fixture_api_http_requests_total[1m]))` | Mide las solicitudes por segundo (`req/s`) desglosadas por ruta y código HTTP (`200`, `400`, `404`, `503`, `504`). |
| **5. Comparación de Latencia entre Bases NoSQL** | `fixture_db_ping_latency_seconds` y promedio de `fixture_db_operation_duration_seconds` | Distingue el comportamiento entre los 6 motores (por ejemplo, lecturas en memoria de Redis frente a consultas a disco/red en Cassandra, MongoDB, Neo4j, InfluxDB o IRIS). La serie de ping solo existe con la base `up`/`degraded`: un hueco indica base caída, no latencia 0. |
| **6. Errores por Flujo y Dependencia** | `sum by (route, codigo) (increase(fixture_api_http_errors_total[5m]))` | Cantidad de errores en los últimos 5 minutos (sube durante una falla y vuelve a 0 tras la recuperación). Distingue errores de validación/ausencia (`400`/`404`) de caídas o timeouts reales de una base (`DEPENDENCIA_NO_DISPONIBLE`, `DEPENDENCIA_TIMEOUT`). |
| **7. Throughput por Base de Datos** | `sum by (db, status) (rate(fixture_db_operations_total[1m]))` | Operaciones de negocio por segundo contra cada adaptador, separadas en `ok` vs error. Los pings de salud no se cuentan. |
| **8. Infraestructura del Nodo (`node-exporter`)** | CPU (`node_cpu_seconds_total`) y RAM (`node_memory_MemAvailable_bytes`) | Diferencia la carga de infraestructura del host de contenedores respecto de las métricas de aplicación de la API (RF4). |

## 4.Cómo exportar o reimportar manualmente

Si no se utiliza el volumen de provisioning, el archivo [`dashboards/fixture2030_war_room.json`](dashboards/fixture2030_war_room.json) puede importarse manualmente desde **Dashboards → New → Import → Upload dashboard JSON file**, seleccionando el datasource `Prometheus`.

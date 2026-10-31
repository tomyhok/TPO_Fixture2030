# Alertas, SLAs y Umbrales Operativos — Fixture 2030 (Hito 13)

Este documento cumple el requisito **RF9** y la **Sección 5.4 (Alertas)** de la consigna del Hito 13, en línea con los conceptos de **SLI, SLO y SLA** de la **Clase 14**. Las reglas están implementadas en [`../prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml) y son evaluadas por Prometheus cada `15s`.

---

## 1. Marco SLI / SLO / SLA del Fixture Mundial 2030

| Concepto | Definición en el Fixture 2030 | Valor de Diseño (TPO) | Valor Medible en Laboratorio |
|---|---|---|---|
| **SLI (Service Level Indicator)** | Métrica cuantitativa observada en Prometheus: disponibilidad (`up`, `fixture_db_up`), latencia `p95` (`fixture_api_http_request_duration_seconds`) y tasa de errores `5xx` (`fixture_api_http_errors_total`). | Medición continua cada `15s` | Medido en vivo desde `http://localhost:8000/metrics` y `node-exporter:9100`. |
| **SLO (Service Level Objective)** | Objetivo técnico interno que el equipo de ingeniería busca sostener para cada indicador. | - Disponibilidad: `99.99%` uptime<br>- Latencia: `p95 < 100ms` (`0.1s`)<br>- Tasa de error `5xx`: `< 0.1%` | En laboratorio local (1 nodo por motor): `fixture_db_up == 1` en los 6 motores y latencia `p95 < 100ms` en lecturas individuales y en el muro optimizado con Redis (`11,1 ms` p95 a 500 ops/s en Hito 12). |
| **SLA (Service Level Agreement)** | Compromiso ante la FIFA y consecuencias operativas si se incumple el SLO durante un partido del Mundial. | Escalamiento inmediato a guardia SRE/NoSQL y activación de contingencias (degradación controlada por módulo, reconstrucción de caché o failover de réplica). | Simulado mediante la prueba de falla controlada (`ejecutar_prueba_controlada.py`) y las reglas de alerta en Prometheus. |

---

## 2. Especificación Detallada de las Reglas de Alerta (Sección 5.4)

### Alerta 1: `BaseDatosNoSQLNoDisponible`

| Atributo | Especificación |
|---|---|
| **Métrica evaluada** | `fixture_db_up{db="<motor>"}` |
| **Condición PromQL** | `fixture_db_up == 0` |
| **Duración mínima (`for`)** | `15s` (un ciclo completo de scraping tras el cambio de estado para evitar falsos positivos por un parpadeo puntual de red). |
| **Severidad** | `critical` |
| **Componente afectado** | El motor NoSQL indicado por la etiqueta `db` (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb` o `iris`). |
| **Quién debe atenderla** | Equipo de **Ingeniería de Datos / DBA NoSQL** de guardia. |
| **Impacto posible en el Fixture** | El módulo asociado a esa base responde `503 Service Unavailable` (`DEPENDENCIA_NO_DISPONIBLE`), pero **no cae toda la plataforma**: gracias al diseño desacoplado de `SaludService.preparacion()` (Hito 11), los otros 5 módulos siguen respondiendo `200 OK`. Por ejemplo, si cae `redis`, no se pueden validar sesiones ni leer el muro precomputado (debiendo ir a Cassandra), pero siguen funcionando equipos (MongoDB), eventos (Neo4j), estadísticas (InfluxDB) y actas (IRIS). |
| **Acción de investigación o recuperación** | 1. Consultar `GET /health/dependencias?refrescar=true` para leer el campo `motivo` (`DEPENDENCIA_NO_DISPONIBLE`, `DEPENDENCIA_TIMEOUT`, `FALTA_CONFIGURACION`).<br>2. Ejecutar `bash ../fixture2030-hito-11-conectividad/scripts/evaluar_conectividad.sh --producto <db>` para aislar la capa rota (TCP, protocolo, credencial o contexto).<br>3. Si el contenedor se detuvo, ejecutar `docker start fixture2030-<db>` y verificar la vuelta de `fixture_db_up` a `1`. |
| **Por qué el umbral es razonable / experimental** | `fixture_db_up` ya incorpora los timeouts por adaptador (`2s`) y la clasificación por capas del Hito 11; un valor `0` sostenido por `15s` confirma que la base dejó de responder o perdió su configuración. |

---

### Alerta 2: `LatenciaAPISuperaSLA100ms`

| Atributo | Especificación |
|---|---|
| **Métrica evaluada** | `fixture_api_http_request_duration_seconds_bucket` |
| **Condición PromQL** | `histogram_quantile(0.95, sum by (le, route) (rate(fixture_api_http_request_duration_seconds_bucket[1m]))) > 0.1` |
| **Duración mínima (`for`)** | `1m` |
| **Severidad** | `warning` |
| **Componente afectado** | Ruta de negocio de la API integrada (`{{ $labels.route }}`) y el motor NoSQL subyacente de esa ruta. |
| **Quién debe atenderla** | Equipo de **Backend API + Ingeniería de Datos**. |
| **Impacto posible en el Fixture** | Los espectadores experimentan demoras superiores al objetivo de diseño de la FIFA (`< 100ms`). En picos de tráfico (como un gol en vivo), una latencia creciente anticipa saturación de conexiones o fan-out excesivo sobre la base antes de que ocurran timeouts (`504`). |
| **Acción de investigación o recuperación** | 1. Observar el panel **"Comparación de Latencia por Base de Datos NoSQL"** en Grafana para distinguir si el aumento ocurre dentro del adaptador (`fixture_db_operation_duration_seconds`) o en la capa HTTP.<br>2. Si la ruta afectada es `/partidos/{codigo_partido}/comentarios` (Cassandra), activar o verificar el **muro precomputado en Redis** demostrado en el Hito 12 (que redujo el `p95` de `31,78 ms` a `11,10 ms` y el `p50` un `88,6%`).<br>3. Si todas las rutas suben a la vez, revisar el panel de **CPU y Memoria (`node-exporter`)** por contención de recursos del host. |
| **Por qué el umbral es razonable / experimental** | El enunciado general del TPO fija explícitamente **latencia `< 100ms` (`0.1s`)**. En el laboratorio local (Hito 11 y 12), las lecturas individuales de los 6 motores midieron entre `1,2 ms` (Redis) y `77,2 ms` (Cassandra), por lo que superar `100 ms` en el percentil 95 durante `1 minuto` indica una degradación real respecto de la línea base medida. |

---

### Alerta 3: `ErroresDependenciaSostenidos`

| Atributo | Especificación |
|---|---|
| **Métrica evaluada** | `fixture_api_http_errors_total{codigo=~"DEPENDENCIA_NO_DISPONIBLE\|DEPENDENCIA_TIMEOUT\|ERROR_INTERNO"}` |
| **Condición PromQL** | `sum by (route, codigo) (rate(fixture_api_http_errors_total{codigo=~"DEPENDENCIA_NO_DISPONIBLE\|DEPENDENCIA_TIMEOUT\|ERROR_INTERNO"}[1m])) > 0.05` |
| **Duración mínima (`for`)** | `30s` |
| **Severidad** | `critical` |
| **Componente afectado** | Flujo de negocio (`{{ $labels.route }}`) y su adaptador de datos. |
| **Quién debe atenderla** | Equipo de **Ingeniería de Datos / Backend SRE**. |
| **Impacto posible en el Fixture** | Solicitudes reales de usuarios están fallando con HTTP `503`, `504` o `500`. A diferencia de los errores `400` (`VALIDACION_ERROR`) o `404` (`RECURSO_NO_ENCONTRADO`), que son respuestas normales de dominio y **se excluyen deliberadamente del filtro de esta alerta**, estos códigos implican que un subsistema no está pudiendo servir lecturas válidas. |
| **Acción de investigación o recuperación** | 1. Identificar el `request_id` en los logs estructurados de la API (`logs/api.log`) correlacionando `dependencia`, `operacion` y `resultado`.<br>2. Si el código es `DEPENDENCIA_TIMEOUT` (`504`), verificar carga del motor (ej. compactación o GC en Cassandra, o consulta sin índice) y evaluar ajuste de timeout o activación de caché.<br>3. Si es `DEPENDENCIA_NO_DISPONIBLE` (`503`), aplicar el protocolo de recuperación del motor afectado. |
| **Por qué el umbral es razonable / experimental** | En operación normal de laboratorio la tasa de errores `5xx` es exactamente `0` (verificado en las corridas de 60.000 operaciones del Hito 12 con `0` errores). Un umbral `> 0.05 err/s` (`≥ 3 errores por minuto`) sostenido por `30s` detecta de inmediato cualquier falla real sin dispararse por errores `400`/`404` del cliente. |

---

### Alerta 4: `TargetMonitoreoCaido`

| Atributo | Especificación |
|---|---|
| **Métrica evaluada** | `up` |
| **Condición PromQL** | `up == 0` |
| **Duración mínima (`for`)** | `30s` (dos ciclos de scraping consecutivos fallidos). |
| **Severidad** | `critical` |
| **Componente afectado** | `fixture-api`, `node-exporter` o `prometheus`. |
| **Quién debe atenderla** | Equipo de **Plataforma / SRE**. |
| **Impacto posible en el Fixture** | Si cae `fixture-api`, ningún cliente externo puede consumir el backend unificado y además se pierde la visibilidad sobre el estado de las 6 bases. Si cae `node-exporter`, se pierde la visibilidad de CPU/RAM del host. |
| **Acción de investigación o recuperación** | 1. Ejecutar `python scripts/verificar_targets.py` para inspeccionar el `lastError` de scraping.<br>2. Si es `fixture-api`, verificar el proceso Uvicorn en el puerto `8000` (`GET /health/live`).<br>3. Si es `node-exporter`, ejecutar `docker compose up -d node-exporter`. |
| **Por qué el umbral es razonable / experimental** | Con `scrape_interval: 15s`, esperar `30s` exige al menos 2 fallos seguidos de recolección HTTP antes de alertar. |

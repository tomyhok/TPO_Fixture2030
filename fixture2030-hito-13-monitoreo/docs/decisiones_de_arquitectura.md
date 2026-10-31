# Decisiones de Arquitectura, Persistencia Políglota y Mejoras Transversales (Hito 13)

Este documento sintetiza y fundamenta todas las decisiones técnicas de la plataforma **Fixture Mundial 2030** para cumplir con los requisitos **RF11, RF12, RF14, RF15** y la **Sección 6.4 (Qué es importante defender)** de la consigna del Hito 13.

---

## 1. Por qué no usar una única estructura o base relacional para todo el Fixture 2030

El Mundial 2030 plantea un escenario con **6 países anfitriones en 3 continentes** (Argentina, Paraguay, Uruguay, España, Portugal y Marruecos), **64 selecciones**, **127 partidos**, **2 a 3 millones de usuarios simultáneos** y picos de **100.000+ operaciones por segundo** (por ejemplo, comentarios y estadísticas tras un gol en vivo) con un objetivo de **latencia `< 100ms`**.

Forzar todos estos flujos sobre un único motor relacional o un único modelo NoSQL generaría cuellos de botella estructurales:
- **Contención de escrituras y locks:** Un muro de comentarios en vivo con decenas de miles de inserciones por segundo saturaría el *buffer pool*, los índices B-Tree y el log transaccional (WAL) de un RDBMS tradicional, degradando al mismo tiempo la lectura de planteles o actas oficiales.
- **Impedancia de modelo:** Recorrer relaciones de múltiples saltos (qué jugadores enfrentaron a qué rivales en qué sedes) requiere *JOINs* recursivos costosos en tablas o agregaciones complejas en documentos, mientras que en un grafo de propiedades (**Neo4j**) se resuelve por punteros libres de índice (*index-free adjacency*).
- **Gestión de estado efímero:** Almacenar millones de sesiones con expiración automática por segundo en disco transaccional desperdicia I/O frente a un motor en memoria con TTL nativo (**Redis**).
- **Series temporales de alta frecuencia:** Ingerir millones de puntos de telemetría minuto a minuto y agregarlos por ventanas de tiempo (`DATE_BIN`) exige compresión columnar por serie temporal (**InfluxDB 3**) en lugar de filas de propósito general.

Por ello adoptamos una arquitectura de **Persistencia Políglota**, donde cada uno de los **6 motores NoSQL** resuelve un patrón de acceso específico y se integra detrás de la **API REST del Hito 10** sin acoplar las bases entre sí.

---

## 2. Defensa Técnica de los 6 Modelos Incorporados (Los 10 Puntos de la Sección 6.4)

### 2.1. MongoDB 7.0 — Modelo Documental (Hito 4)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Fichas de las **64 selecciones nacionales** (`equipos`) y **1.472 futbolistas** (`jugadores`) con atributos semirrígidos y validación JSON Schema. |
| 2 | **Consultas / accesos que motivaron su elección** | Lectura de la ficha completa de una selección por su código ISO (`GET /equipos/{codigo_iso}`), filtros por confederación/grupo/anfitrión y listado de plantel por equipo y posición. |
| 3 | **Modelo utilizado** | **Documental** (BSON). |
| 4 | **Estructura concreta implementada** | Dos colecciones validadas (`equipos` con índice único en `codigo_iso` e índice en `grupo`; `jugadores` con índice único en `id_jugador` e índice compuesto `{equipo_iso: 1, posicion: 1}`). Se separaron en dos colecciones para no reescribir el documento del equipo al actualizar un jugador individual. |
| 5 | **Cómo carga y recupera información** | Carga idempotente mediante `bulkWrite` + `updateOne(..., {upsert: true})` en [`02-carga.js`](../../fixture2030-mongoDB/init-scripts/02-carga.js). Recuperación en `O(log N)` vía `IXSCAN` verificado con `.explain("executionStats")` (`totalDocsExamined: 1`). |
| 6 | **Escalabilidad y distribución considerada** | **Replica Set** (Primary-Secondary-Secondary) distribuido entre las regiones anfitrionas: escrituras en el primario y lecturas locales de catálogo escalables en secundarios dado que las plantillas cambian con baja frecuencia. |
| 7 | **Consistencia requerida** | **CP** (en el modelo CAP de MongoDB con primario único): consistencia fuerte en el primario y lectura consistente de catálogos oficiales. |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | En el laboratorio (1 nodo), la ruta `/equipos/{codigo_iso}` devuelve `503 DEPENDENCIA_NO_DISPONIBLE` en `< 2s` sin afectar los otros 5 módulos. En producción con Replica Set, elección automática de nuevo primario (failover en segundos). |
| 9 | **Trade-off aceptado** | Mantener `equipos` y `jugadores` en colecciones separadas evita documentos gigantes, pero si se requiere cruzar datos fuera del índice se necesitaría `$lookup` o dos lecturas. |
| 10 | **Evidencia en el repositorio** | [`fixture2030-mongoDB/docs/Grupo_4_Hito_4_Decisiones_Documentales_Fixture2030.md`](../../fixture2030-mongoDB/docs/Grupo_4_Hito_4_Decisiones_Documentales_Fixture2030.md) y planes `IXSCAN` verificados; lectura real en `3,5 ms` (Hito 11). |

---

### 2.2. Neo4j — Modelo de Grafos de Propiedades (Hito 5)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Red conectada de `:Equipo` (64), `:Jugador` (1.472), `:Partido`, `:Sede` y `:Evento` (1.542 nodos y 1.480 relaciones en total). |
| 2 | **Consultas / accesos que motivaron su elección** | Recorridos relacionales de múltiples saltos: cronología de eventos de un partido con su autor (`GET /partidos/{codigo_partido}/eventos`), cruces de rivales, jugadores que compitieron en una sede y caminos de enfrentamientos. |
| 3 | **Modelo utilizado** | **Grafo de Propiedades** consultado con Cypher parametrizado. |
| 4 | **Estructura concreta implementada** | Restricciones de unicidad (`UNIQUENESS`) sobre `Equipo.codigo_iso`, `Jugador.id_jugador`, `Partido.codigo`, `Sede.nombre` y `Evento.id_evento`. Relaciones tipadas `:PERTENECE_A`, `:DISPUTA`, `:SE_JUEGA_EN`, `:OCURRE_EN` y `:PROTAGONIZA`. |
| 5 | **Cómo carga y recupera información** | Carga idempotente con `MERGE` desde los JSON del Hito 4 ([`carga.cypher`](../../fixture2030-neo4j/queries/carga.cypher)). Recuperación mediante patrón `(p:Partido {codigo: $codigo})<-[:OCURRE_EN]-(e:Evento)<-[:PROTAGONIZA]-(j:Jugador)` en [`neo4j_adapter.py`](../../fixture2030-hito-10-api-integrada/app/adapters/neo4j_adapter.py). |
| 6 | **Escalabilidad y distribución considerada** | Escalamiento vertical del grafo en memoria (*page cache*) y réplicas de lectura (Read Replicas en arquitectura Raft de Neo4j) para absorber consultas de recorrido durante los partidos. |
| 7 | **Consistencia requerida** | **CA / CP** (transacciones ACID sobre el líder Raft; consistencia causal en réplicas de lectura). |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | Si Bolt (`:7687`) cae o la base `NEO4J_DATABASE` no existe, el adaptador traduce la excepción a `503 DEPENDENCIA_NO_DISPONIBLE` (corregido en el Hito 11 para no devolver `500`). |
| 9 | **Trade-off aceptado** | Excelente rendimiento en travesías de relaciones locales (`~5,9 ms` en Hito 11), pero menor capacidad de particionamiento horizontal (*sharding*) de escritura masiva que Cassandra. Por eso no se guardan aquí los millones de comentarios. |
| 10 | **Evidencia en el repositorio** | [`fixture2030-neo4j/docs/evidencia/revision_2026-10-19/README.md`](../../fixture2030-neo4j/docs/evidencia/revision_2026-10-19/README.md) y [`ejecucion.json`](../../fixture2030-neo4j/docs/evidencia/revision_2026-10-19/ejecucion.json). |

---

### 2.3. Apache Cassandra — Modelo Columnar de Columnas Anchas (Hito 6 y Hito 12)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Comentarios masivos en vivo de espectadores durante los partidos (`1M+` comentarios en pruebas de volumen del Hito 6; `100.000+` en pruebas del Hito 12). |
| 2 | **Consultas / accesos que motivaron su elección** | Escritura intensiva durante picos de partido (goles, penales) y lectura paginada de los comentarios más recientes de un partido en una ventana temporal (`GET /partidos/{codigo_partido}/comentarios`). |
| 3 | **Modelo utilizado** | **Columnar de Columnas Anchas** (*Wide-Column* / Particionado por clave compuesta + Clustering). |
| 4 | **Estructura concreta implementada** | Cuatro tablas desnormalizadas por consulta (`comentarios_por_partido`, `comentarios_por_usuario`, `comentarios_moderacion`, `metricas_comentarios_partido`). En `comentarios_por_partido`, la clave primaria es `((codigo_partido, ventana, shard), id_comentario)` con `CLUSTERING ORDER BY (id_comentario DESC)` (`TIMEUUID`). El *bucketing* por minuto (`ventana`) y `shard` (`0..3`) evita *hot partitions* en un gol. |
| 5 | **Cómo carga y recupera información** | Escritura *append-only* en Memtable + CommitLog sin *read-before-write*. Lectura por los 4 shards de la ventana y ordenación por `TIMEUUID` con cursor paginado. |
| 6 | **Escalabilidad y distribución considerada** | Arquitectura **Peer-to-Peer sin maestro** (*masterless ring*) con `NetworkTopologyStrategy` multi-datacenter (Sudamérica y Europa/África), escalable linealmente en escrituras agregando nodos al anillo. |
| 7 | **Consistencia requerida** | **AP** en el Teorema CAP: se prioriza disponibilidad y baja latencia de escritura durante el partido (`LOCAL_ONE` / `LOCAL_QUORUM`), aceptando consistencia eventual en el muro de comentarios. |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | En un clúster multi-nodo, *Hinted Handoff* y otro coordinador absorben la caída de un nodo sin interrumpir escrituras. En el laboratorio (1 nodo con volumen nombrado `fixture2030_cassandra_data`), si el nodo cae, la API responde `503` en `/comentarios` aislando el resto. |
| 9 | **Trade-off aceptado** | El *sharding* (`4 shards × 3 ventanas = 12 consultas` en el escenario del Hito 12) protege las escrituras pero introduce un **fan-out de lectura** que encarece la lectura directa desde el cliente. Este trade-off motivó la optimización transversal con Redis del Hito 12. |
| 10 | **Evidencia en el repositorio** | [`fixture2030-cassandra/docs/evidencia.md`](../../fixture2030-cassandra/docs/evidencia.md), migración verificada con SHA-256 de 147 archivos en [`migracion_volumen.json`](../../fixture2030-cassandra/docs/revision_2026-10-19/migracion_volumen.json) y benchmark del Hito 12. |

---

### 2.4. Redis — Modelo Clave-Valor en Memoria (Hito 7 y Hito 12)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Sesiones activas de usuarios (`sesion:<id>`), caché de lectura (`cache:*`), contadores atómicos en vivo y el muro precomputado de comentarios (`muro:<partido>` del Hito 12). |
| 2 | **Consultas / accesos que motivaron su elección** | Validación sub-milisegundo de sesión activa (`GET /sesiones/{id_sesion}` con `HGETALL` + `TTL` en pipeline) y absorción de lecturas repetitivas en picos de concurrencia. |
| 3 | **Modelo utilizado** | **Clave-Valor en Memoria** con estructuras ricas (`Hash`, `String`, `List`, `Sorted Set`). |
| 4 | **Estructura concreta implementada** | Hashes `sesion:<id>` con `EXPIRE 1800` (30 min), persistencia híbrida (`appendonly yes` + `save 60 1`), `maxmemory 256mb` y política **`noeviction`** (corregida en la revisión del Hito 7 para no expulsar sesiones activas antes de su vencimiento como ocurría con `volatile-lru`). |
| 5 | **Cómo carga y recupera información** | En la API (`redis_adapter.py`), un pipeline único ejecuta `HGETALL` y `TTL` en un solo viaje de red (`~1,2 ms`). En el Hito 12, el muro se lee con `LRANGE muro:P-001 0 19` (1 operación en vez de 12 consultas a Cassandra). |
| 6 | **Escalabilidad y distribución considerada** | Separación lógica (y en producción, instancias separadas) entre el **store de sesiones** (`noeviction` + réplica) y la **instancia de caché descartable** (`allkeys-lru`). |
| 7 | **Consistencia requerida** | Operaciones atómicas en hilo único (*single-threaded event loop*) sobre el nodo primario; replicación asíncrona hacia réplicas. |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | Si cae el store de sesiones, `/sesiones/{id}` devuelve `503`. Si cae o expira el muro precomputado (`muro:*`), se reconstruye desde la fuente de verdad (**Cassandra**) usando un lock distribuido (`SET lock:muro:<p> NX EX 2`). |
| 9 | **Trade-off aceptado** | Con una única instancia en laboratorio y política `noeviction`, si se llenan los 256 MB fallarán nuevas escrituras hasta que expiren claves por TTL (por eso se acota el muro con `LTRIM 0 99` y `TTL 60s`, ocupando `< 2 MiB`). |
| 10 | **Evidencia en el repositorio** | [`fixture2030-redis/docs/memoria_y_escalabilidad.md`](../../fixture2030-redis/docs/memoria_y_escalabilidad.md), [`politica.json`](../../fixture2030-redis/docs/revision_2026-10-19/politica.json) y reducción del `88,6%` en latencia `p50` en el Hito 12. |

---

### 2.5. InfluxDB 3 Core — Modelo de Series Temporales (Hito 8)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Series temporales de estadísticas en vivo de los partidos (`estadisticas_partido`): posesión, pases completados, tiros, faltas y espectadores conectados. |
| 2 | **Consultas / accesos que motivaron su elección** | Consulta de evolución estadística por ventana temporal con agregación/downsampling (`GET /partidos/{codigo_partido}/estadisticas?desde=...&hasta=...&resolucion=1m`). |
| 3 | **Modelo utilizado** | **Series Temporales Multidimensional** (Measurement + Tags indexados + Fields numéricos + Timestamp). |
| 4 | **Estructura concreta implementada** | Measurement `estadisticas_partido` con **tags de baja cardinalidad** (`partido_id`, `equipo_id`, `fase`) y **fields numéricos** (`posesion_pct`, `pases_completados`, `tiros`, `usuarios_activos`). Se evitó incluir identificadores de alta cardinalidad (como `usuario_id`) en los tags para prevenir explosión de series (*cardinality explosion*). |
| 5 | **Cómo carga y recupera información** | Ingesta por lotes en formato **Line Protocol** (`/api/v3/write_lp`) y consulta SQL analítica parametrizada con `DATE_BIN(INTERVAL '...', time)` sobre motor columnar Apache Arrow / Parquet (`/api/v3/query_sql`). |
| 6 | **Escalabilidad y distribución considerada** | Almacenamiento columnar comprimido respaldado por Object Store, separando cómputo de ingesta y consulta analítica, con políticas de retención y downsampling histórico. |
| 7 | **Consistencia requerida** | Consistencia eventual de ingesta por lotes (*batching*) orientada a alto throughput de escritura y lecturas agregadas rápidas. |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | Si falta el token `.influxdb3-token`, el diagnóstico la reporta como `not_configured` sin bloquear el arranque de la API; si el servidor HTTP `:8181` no responde, devuelve `503`/`504` en `/estadisticas`. |
| 9 | **Trade-off aceptado** | Optimizado para escritura append-only por tiempo y agregaciones por rango (`DATE_BIN`), pero no apto para transacciones relacionales ni actualizaciones puntuales de registros individuales. |
| 10 | **Evidencia en el repositorio** | [`fixture2030-influxDB/README.md`](../../fixture2030-influxDB/README.md), [`08_entorno.json`](../../fixture2030-influxDB/docs/evidencia/08_entorno.json) y [`09_conectividad.txt`](../../fixture2030-influxDB/docs/evidencia/09_conectividad.txt). |

---

### 2.6. InterSystems IRIS — Modelo Orientado a Objetos / Multimodelo (Hito 9)

| # | Criterio | Definición en nuestro sistema |
|---|---|---|
| 1 | **Tipo de dato almacenado** | Entidades complejas con lógica e invariantes encapsulados: **Actas Oficiales de Partido** (`Fixture.Partido`), **Árbitros** (`Fixture.Arbitro`), **Técnicos** (`Fixture.Tecnico`) y **Eventos Oficiales** (`Fixture.EventoPartido`). |
| 2 | **Consultas / accesos que motivaron su elección** | Recuperación del acta oficial completa de un partido (`GET /partidos-oficiales/{codigo_partido}`) garantizando integridad estructural y reglas de negocio del dominio FIFA. |
| 3 | **Modelo utilizado** | **Orientado a Objetos / Multimodelo** (clases persistentes `%Persistent` con proyección dual Objeto + SQL). |
| 4 | **Estructura concreta implementada** | Jerarquía de herencia (`Fixture.Persona` → `Fixture.Arbitro` y `Fixture.Tecnico`), relación padre-hijo (`Fixture.Partido` ↔ `Fixture.EventoPartido` con cardinalidad `children`/`parent`) y regla de dominio encapsulada en **`Partido.AgregarEvento()`**: si el partido está en estado `"Finalizado"`, rechaza agregar nuevos eventos al acta oficial. |
| 5 | **Cómo carga y recupera información** | Creación y validación de invariantes desde ObjectScript (`%Save()` en cascada padre-hijo en [`demo.mac`](../../fixture2030-iris/scripts/demo.mac)); lectura desde la API integrada mediante **DB-API y SQL parametrizado** sobre la proyección SQL de `Fixture.Partido` y `Fixture.EventoPartido` (`iris_adapter.py`). |
| 6 | **Escalabilidad y distribución considerada** | El volumen de actas oficiales es bajo y acotado (`127 partidos` en todo el Mundial), pero su criticidad normativa es máxima: se prioriza un clúster con espejo síncrono/asíncrono (*IRIS Mirroring*) para alta disponibilidad transaccional. |
| 7 | **Consistencia requerida** | **ACID / Consistencia Fuerte (CP)**: un acta arbitral oficial no admite consistencia eventual ni pérdida de eventos sancionados. |
| 8 | **Qué ocurre ante una falla o indisponibilidad** | El adaptador ejecuta las consultas en un ejecutor con límite de tiempo propio (para protegerse de bloqueos del driver nativo documentados en el Hito 11) y devuelve `503`/`504` si el puerto Superserver `1972` no está disponible. |
| 9 | **Trade-off aceptado** | Mayor acoplamiento al motor y menor elasticidad horizontal masiva que Cassandra, lo cual es irrelevante para 127 actas oficiales pero decisivo para garantizar invariantes de dominio y herencia. |
| 10 | **Evidencia en el repositorio** | [`fixture2030-iris/README.md`](../../fixture2030-iris/README.md) y [`compilacion_y_demo.txt`](../../fixture2030-iris/docs/revision_2026-10-19/compilacion_y_demo.txt) (`antes=2, despues=2, REGLA_OK`). |

---

## 3. Relación entre las Métricas Observadas y los Objetivos del TPO (RF11)

| Objetivo del TPO | Meta de Diseño (Mundial 2030) | Qué Métrica lo Observa en Hito 13 | Evidencia Medida en el Repositorio |
|---|---|---|---|
| **Concurrencia** | 2–3 millones de espectadores simultáneos | `fixture_api_in_flight_requests` (API) + pruebas multihilo/multiproceso en Redis (Hito 7) y Cassandra+Redis (Hito 12, 50 usuarios concurrentes sostenidos). | En Hito 7 (`08_prueba_concurrencia.txt`) y Hito 12 (`comparacion.md`): `0` errores de concurrencia y `0` duplicados al reconstruir el muro con lock `SET NX EX`. |
| **Throughput** | 100.000+ operaciones/seg en picos globales | `sum(rate(fixture_api_http_requests_total[1m]))` y `sum by (db) (rate(fixture_db_operations_total[1m]))`. | En una única notebook local (Hito 12): el muro directo en Cassandra alcanzó `819 – 1.088 ops/s`, y con la optimización en Redis escaló a **`6.737,3 ops/s`** (hasta **14× más throughput** en un solo nodo). |
| **Latencia** | `< 100ms` (`0.1s`) | `histogram_quantile(0.95, ... fixture_api_http_request_duration_seconds_bucket)` y `fixture_db_operation_duration_seconds`. | En Hito 11, las 6 lecturas individuales midieron entre `1,2 ms` (Redis) y `77,2 ms` (Cassandra), todas `< 100ms`. Bajo carga fija de `500 ops/s` (Hito 12), la optimización bajó el `p50` de `14,70 ms` a **`1,67 ms`** y el `p95` de `31,78 ms` a **`11,10 ms`**. |
| **Disponibilidad** | `99.99%` uptime | `up`, `fixture_db_up{db}` y `GET /health/ready`. | `SaludService.preparacion()` mantiene la API `ready` (`200 OK`) mientras al menos 1 de los 6 motores esté activo, aislando la caída de una base (`503` solo en su ruta) como demuestra la prueba controlada del Hito 13. |
| **Distribución y Recuperación** | 6 países anfitriones (3 continentes) y tolerancia a fallos | `fixture_db_status_info`, serie temporal antes/durante/después en `evidencia/prueba_de_falla.json` y `fallo_controlado.sh` (Hito 11). | Persistencia verificada sobre volúmenes Docker (`fixture2030_cassandra_data`, `mongodb_data`, etc.) y recuperación automática de `fixture_db_up` de `0` a `1` tras reiniciar el servicio sin pérdida de datos. |

---

## 4. Análisis de Mejoras Transversales a partir de la Evidencia (RF12)

A partir de las mediciones de los Hitos 6 a 13, analizamos e implementamos **cuatro mejoras transversales** concretas:

### Mejora 1 (Implementada y Medida en Hito 12): Muro precomputado en Redis (`LPUSHX` + `LTRIM` + Lock) delante de Cassandra
- **Evidencia que la motivó:** En la línea base del Hito 12, leer el muro de comentarios hacía un *fan-out* de **12 consultas a Cassandra** (`3 ventanas × 4 shards`). A `500 ops/s`, eso generaba `4.800 consultas/s` a Cassandra, consumiendo `77%` de CPU en Cassandra y `100%` en el cliente con `p99 = 58,83 ms`.
- **Cambio transversal:** Combinar Cassandra (fuente de verdad de escritura masiva) con una lista acotada en Redis (`muro:<partido>`, últimos 100 comentarios, `TTL 60s`, actualizando con `LPUSHX` + `LTRIM 0 99` y reconstruyendo en *cache miss* con lock `SET NX EX 2`).
- **Resultado medido:** Reducción del **88,6% en latencia `p50`** (`14,70 ms → 1,67 ms`), **70,1% en `p99`** (`58,83 ms → 17,57 ms`), **80% menos CPU en Cassandra** (`77% → 15,5%`) y un aumento de capacidad máxima de `484 ops/s` a **`6.737 ops/s`**.

### Mejora 2 (Implementada en Hito 7): Separación conceptual entre Sesiones y Caché (`noeviction`)
- **Evidencia que la motivó:** Usar `volatile-lru` en una instancia compartida de Redis permitía que ante presión de memoria se desalojaran claves con TTL, incluyendo sesiones activas de usuarios autenticados.
- **Cambio transversal:** Configurar `maxmemory-policy noeviction` en la instancia de laboratorio para proteger las sesiones activas hasta que cumplan su TTL de 30 minutos, y documentar la separación en dos instancias Redis independientes en producción (una `noeviction` para sesiones y otra `allkeys-lru` para caché/muros reconstruibles).

### Mejora 3 (Implementada en Hito 11 y aprovechada en Hito 13): Caché de Diagnóstico Profundo (`HEALTH_CACHE_TTL_S = 10s`) con Lock de Concurrencia
- **Evidencia que la motivó:** Si Prometheus (`scrape_interval: 15s`), un balanceador de carga (`/health/ready`) y operadores humanos consultan el estado de salud simultáneamente, ejecutar `ping()` en las 6 bases en cada request multiplicaría la carga artificialmente sobre los motores.
- **Cambio transversal:** En [`salud_service.py`](../../fixture2030-hito-10-api-integrada/app/services/salud_service.py), un `threading.Lock()` y una ventana de reutilización de `10s` garantizan que `/metrics`, `/health/ready` y `/health/dependencias` compartan el resultado reciente sin golpear las 6 bases más de una vez cada 10 segundos.

### Mejora 4 (Propuesta para siguiente iteración de Observabilidad y Analítica): Exporters Nativos por Motor + Proyección a Data Mart
- **Observabilidad:** Incorporar en un perfil opcional de Docker Compose (`--profile exporters`) los contenedores `percona/mongodb_exporter`, `oliver006/redis_exporter` y `bitnami/cassandra-exporter` para correlacionar en Grafana las métricas del adaptador de la API con métricas internas del motor (compactaciones SSTable, *evictions* y *page cache*).
- **Analítica (Data Mart del Hito 12):** Mantener las 6 bases NoSQL exclusivamente para la carga operacional en vivo y proyectar asíncronamente (vía CDC / lotes post-partido) los comentarios, eventos y estadísticas hacia el **Data Mart estrella** diseñado en [`fixture2030-hito-12-carga-optimizacion/docs/integracion_data_mart.md`](../../fixture2030-hito-12-carga-optimizacion/docs/integracion_data_mart.md), evitando que consultas analíticas de la FIFA bloqueen la operación en tiempo real.

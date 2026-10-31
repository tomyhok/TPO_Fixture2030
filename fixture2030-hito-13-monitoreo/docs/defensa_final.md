# Defensa Final ante la FIFA — Pregunta Central y Banco de Respuestas Técnicas (Hito 13)

Este documento prepara al equipo para la **Defensa Final del TPO (Sección 6 y Sección 11)** y cumple los requisitos **RF13, RF14, RF15 y RF16**. Relaciona cada posible pregunta de la representación de la FIFA con la decisión técnica tomada y con la consulta, endpoint, dashboard o evidencia concreta del repositorio que la demuestra.

---

## 1. Respuesta a la Pregunta Central del TPO (Sección 11)

> **¿Por qué esta combinación de modelos, estructuras, estrategias de distribución y mecanismos de observabilidad resulta adecuada para el Fixture Mundial 2030 bajo las condiciones planteadas?**

La plataforma del **Fixture Mundial 2030** no enfrenta un único problema de datos, sino **seis patrones de acceso con requisitos de volumen, velocidad, estructura y consistencia contrapuestos**:

1. **Consultas de catálogo jerárquico de baja mutación y lectura intensiva** (64 selecciones y 1.472 jugadores) → resueltas con **MongoDB (Documental)** mediante índices `IXSCAN` y réplicas de lectura regionales.
2. **Recorridos de relaciones deportivas y caminos entre entidades** (partidos, sedes, rivales y eventos) → resueltos con **Neo4j (Grafo)** evitando *JOINs* recursivos mediante adyacencia libre de índice.
3. **Ingesta masiva de comentarios en vivo durante picos de gol** (`1M+` comentarios) → resuelta con **Cassandra (Columnar de columnas anchas)** particionando por `(codigo_partido, ventana, shard)` y ordenando por `TIMEUUID`, priorizando **AP** (disponibilidad de escritura y particionado horizontal sin nodo maestro).
4. **Estado efímero de millones de sesiones con vencimiento automático y aceleración de lecturas calientes** → resuelto con **Redis (Clave-Valor en memoria)** separando la protección de sesiones (`noeviction` + `TTL 1800s`) del muro precomputado descartable (`muro:<partido>` con `LPUSHX`, `LTRIM 0 99` y `TTL 60s`), que redujo en **88,6%** la latencia de lectura y en **80%** el uso de CPU de Cassandra en las pruebas de carga del Hito 12.
5. **Telemetría y estadísticas minuto a minuto en tiempo real** (`10M+` puntos) → resueltas con **InfluxDB 3 Core (Series Temporales)** con tags de baja cardinalidad y agregación columnar `DATE_BIN`.
6. **Actas arbitrales oficiales con reglas normativas estrictas** (127 partidos) → resueltas con **InterSystems IRIS (Orientado a Objetos / Multimodelo)** encapsulando herencia (`Persona → Arbitro / Tecnico`), composición padre-hijo y la regla invariante `Partido.AgregarEvento` que impide adulterar un partido `Finalizado` (**CP / ACID**).

Finalmente, la **API REST Integrada (Hito 10)** desacopla a los clientes de los drivers nativos, el **Diagnóstico por Capas y Readiness (Hito 11)** garantiza que la caída de una base no arrastre a las otras cinco, y el **Monitoreo con Prometheus y Grafana (Hito 13)** permite observar en tiempo real la disponibilidad (`fixture_db_up`), latencia frente al SLA de `< 100ms`, throughput y errores de cada subsistema.

---

## 2. Banco de Respuestas a las 14 Preguntas de la FIFA (Sección 6.5 y RF16)

### 1. ¿Por qué eligieron este modelo para este tipo de dato?
- **Respuesta:** Cada modelo se eligió por el **patrón de acceso dominante** (Hitos 1 y 2):
  - **Documental (MongoDB):** cuando se lee la entidad agregada completa por clave (`codigo_iso`).
  - **Grafo (Neo4j):** cuando el valor está en las aristas y saltos entre nodos (`Partido ← Evento ← Jugador`).
  - **Columnar (Cassandra):** cuando domina la escritura masiva distribuida particionada por clave y ordenada por tiempo (`TIMEUUID`).
  - **Clave-Valor (Redis):** cuando se requiere latencia sub-milisegundo en memoria y expiración nativa (`TTL`).
  - **Series Temporales (InfluxDB):** cuando toda consulta filtra y agrega por intervalos de tiempo (`DATE_BIN`).
  - **Objetos (IRIS):** cuando existen jerarquías de clases e invariantes transaccionales encapsulados en métodos de dominio (`AgregarEvento`).
- **Cómo demostrarlo en el repo:** Mostrar la tabla en [`decisiones_de_arquitectura.md`](decisiones_de_arquitectura.md) y los 6 adaptadores en [`fixture2030-hito-10-api-integrada/app/adapters/`](../../fixture2030-hito-10-api-integrada/app/adapters/).

### 2. ¿Qué consulta sería costosa con otra estructura?
- **Respuesta (3 ejemplos concretos del repo):**
  1. **En Cassandra o Redis hacer recorridos de 3 saltos** (ej. *«¿qué jugadores de qué selecciones compitieron en la misma sede?»*): exigiría múltiples lecturas secuenciales en la aplicación y cruces en memoria, mientras que en **Neo4j** ([`consultas_grafo.cypher`](../../fixture2030-neo4j/queries/consultas_grafo.cypher)) es un único `MATCH` de grafo resuelto en `< 6 ms`.
  2. **En MongoDB o SQL insertar miles de comentarios por segundo sobre el mismo partido en un pico de gol:** generaría contención de locks e índices B-Tree sobre la misma fila/documento del partido, mientras que **Cassandra** escribe en `Memtable + CommitLog` repartido en 4 shards por minuto.
  3. **En Cassandra leer el muro en vivo directamente con 500 ops/s sin caché:** requiere un fan-out de 12 consultas por lectura (`4.800 consultas/s`), mientras que el muro precomputado en **Redis** (`LRANGE muro:P-001 0 19`) lo resuelve en 1 sola operación en `1,67 ms` (`p50`).

### 3. ¿Cómo se distribuyen los datos?
- **Respuesta:**
  - **Cassandra:** Particionamiento por hash consistente (Murmur3Partitioner) sobre la clave de partición compuesta `(codigo_partido, ventana, shard)`. El campo `ventana` (`YYYYMMDDHHMM`) agrupa por minuto y `shard` (`0..3`) divide cada minuto en 4 particiones independientes para evitar *hotspots*.
  - **MongoDB:** Replica Set multi-región para el catálogo (1.536 documentos totales que caben íntegramente en RAM de cada nodo), con opción de sharding por `equipo_iso` si creciera el historial.
  - **InfluxDB:** Particionado temporal por archivos Parquet e indexado por tags de baja cardinalidad (`partido_id`, `equipo_id`).
- **Cómo demostrarlo en el repo:** [`fixture2030-cassandra/scripts/02-tablas.cql`](../../fixture2030-cassandra/scripts/02-tablas.cql) y [`fixture2030-cassandra/docs/modelo_tabular.md`](../../fixture2030-cassandra/docs/modelo_tabular.md).

### 4. ¿Qué sucede si se cae un nodo o una región?
- **Respuesta:**
  - **En la capa de aplicación (API Integrada, Hitos 10–13):** Cada ruta depende exclusivamente de su adaptador. Si cae un motor completo (ej. Redis o MongoDB), `GET /health/ready` sigue respondiendo `200 OK` (`estado="degraded"`), la ruta afectada devuelve `503 DEPENDENCIA_NO_DISPONIBLE` en `< 2s`, `fixture_db_up` baja a `0` en Prometheus disparando la alerta `BaseDatosNoSQLNoDisponible`, y **los otros 5 módulos continúan operando normalmente**.
  - **En producción multi-región:** Los sistemas **AP** (Cassandra con `NetworkTopologyStrategy` `RF=3` por DC) siguen aceptando lecturas y escrituras locales con `LOCAL_QUORUM`; los sistemas **CP** (MongoDB, Neo4j, IRIS) eligen un nuevo primario en la región con mayoría de votos.
- **Cómo demostrarlo en el repo:** [`evidencia/prueba_de_falla.md`](../evidencia/prueba_de_falla.md) y `bash scripts/ejecutar_prueba_controlada.sh`.

### 5. ¿Qué garantía de consistencia necesita este módulo?
- **Respuesta:**
  - **Consistencia Fuerte (ACID / CP):** **IRIS** (actas arbitrales oficiales: no puede agregarse un gol a un partido `Finalizado`) y **MongoDB** (catálogo oficial de selecciones).
  - **Consistencia Eventual Acotada (AP):** **Cassandra + Redis** en el muro de comentarios en vivo y **InfluxDB** en las estadísticas de telemetría: que un comentario o porcentaje de posesión tarde entre 1 y 60 segundos en reflejarse en otra región es aceptable a cambio de no bloquear nunca la escritura durante el partido.

### 6. ¿Qué parte de la respuesta puede ser eventual?
- **Respuesta:** El muro de comentarios en vivo (`GET /partidos/{codigo}/comentarios`) y las estadísticas agregadas por minuto (`GET /partidos/{codigo}/estadisticas`). En el Hito 12 demostramos que con el muro precomputado en Redis (`TTL 60s`), un comentario escrito mientras el muro se está reconstruyendo puede demorar hasta `60s` en aparecer en la caché, pero queda inmediatamente persistido en Cassandra (fuente de verdad).

### 7. ¿Dónde se encuentra el cuello de botella?
- **Respuesta:** En el Hito 12 triangulamos experimentalmente el cuello de botella del flujo más exigente (el muro de comentarios en vivo):
  - Medimos con `nodetool proxyhistograms` que cada consulta individual dentro de Cassandra tardaba apenas **`0,060 ms` (`p50`)**, mientras que la lectura completa del muro en el cliente tardaba **`9,78 a 14,70 ms` (`p50`)**.
  - El cuello de botella estaba en el **fan-out de 12 consultas por lectura** (serialización, red y deserialización en Python con el GIL). Al reducir esas 12 consultas a 1 sola lectura `LRANGE` en Redis, la latencia `p50` bajó un **88,6%** y el CPU de Cassandra bajó un **80%**.
- **Cómo demostrarlo en el repo:** [`fixture2030-hito-12-carga-optimizacion/docs/hipotesis_y_optimizacion.md`](../../fixture2030-hito-12-carga-optimizacion/docs/hipotesis_y_optimizacion.md).

### 8. ¿Cómo distinguen que el problema está en la API y no en la base?
- **Respuesta:** Mediante tres mecanismos complementarios implementados en los Hitos 10, 11 y 13:
  1. **En Prometheus y Grafana (Hito 13):** Comparamos el histograma HTTP total (`fixture_api_http_request_duration_seconds`) contra el histograma del adaptador (`fixture_db_operation_duration_seconds`) y contra el endpoint `/health/live` (que no toca ninguna base).
  2. **Por código de estado y error semántico:** Un `400 VALIDACION_ERROR` se rechaza en la API sin tocar la base (`fixture_db_operations_total` no sube); un `503 DEPENDENCIA_NO_DISPONIBLE` o `504 DEPENDENCIA_TIMEOUT` identifica en `detalles: [{"dependencia": "<motor>"}]` y en `fixture_db_operations_total{status!="ok"}` qué base falló.
  3. **Con el evaluador de 9 capas del Hito 11 (`evaluar_conectividad.sh`):** Verifica Configuración → DNS → TCP → Protocolo → Autenticación → Autorización → Contexto → Lectura nativa → Endpoint API.

### 9. ¿Qué métrica observarían primero ante aumento de latencia?
- **Respuesta:**
  1. Primero, el panel **"Estado de Salud por Base de Datos (`fixture_db_up`)"** y **"Comparación de Latencia por Base de Datos NoSQL (`fixture_db_operation_duration_seconds`)"** en Grafana para identificar cuál de los 6 motores subió su tiempo de respuesta.
  2. Segundo, el panel **"Volumen de Operaciones (`rate(fixture_api_http_requests_total[1m])`)"** para ver si el aumento de latencia se debe a un pico de tráfico en una ruta específica.
  3. Tercero, el panel **"Infraestructura del Nodo (`node-exporter`)"** para verificar si hay saturación de CPU o RAM en el host.

### 10. ¿Qué evidencia tienen de que la optimización funcionó?
- **Respuesta:** En [`fixture2030-hito-12-carga-optimizacion/docs/evidencia/comparacion.md`](../../fixture2030-hito-12-carga-optimizacion/docs/evidencia/comparacion.md), bajo exactamente la misma carga fija (`500 ops/s`, 50 usuarios, 120s, semilla `2030`, 60.000 operaciones totales):
  - Latencia lectura `p50`: de **`14,70 ms` a `1,67 ms` (`-88,6%`)**.
  - Latencia lectura `p95`: de **`31,78 ms` a `11,10 ms` (`-65,1%`)**.
  - Latencia lectura `p99`: de **`58,83 ms` a `17,57 ms` (`-70,1%`)**.
  - CPU de Cassandra: de **`77%` a `15,5%` (`-80%`)**.
  - Tasa de aciertos en Redis: **`99,6%` (`47.727 hits / 168 misses`)**, con `0` errores y `100%` de integridad de escrituras verificada en Cassandra.

### 11. ¿Qué cambiarían si el tráfico se multiplica?
- **Respuesta:**
  1. Escalar horizontalmente las réplicas sin estado (*stateless*) de `fixture-api` detrás de un balanceador que consuma `/health/ready`.
  2. Separar físicamente Redis en dos clústeres independientes: uno para sesiones (`noeviction`) y otro para caché de muros (`allkeys-lru` con réplicas de lectura).
  3. Ampliar el anillo de Cassandra en cada región anfitriona y ajustar el número de `shards` por ventana de minuto (por ejemplo de `4` a `16` shards para finales del Mundial).
  4. Desacoplar las escrituras de comentarios mediante una cola de mensajería (Kafka / Redis Streams) si el pico supera la capacidad de ingesta síncrona.

### 12. ¿Qué se perdería o retrasaría durante una falla?
- **Respuesta:**
  - **Si cae Redis (instancia de caché de muro):** No se pierde ningún comentario porque Cassandra es la fuente de verdad; solo aumenta la latencia de lectura del muro (volviendo a `~14 ms` `p50`) mientras dura la caída.
  - **Si cae Redis (instancia de sesiones):** No se pueden validar ni crear sesiones hasta recuperar el servicio o promover su réplica; las claves ya persistidas en AOF (`appendonly yes`) se recuperan al reiniciar.
  - **Si se reconstruye un muro vencido en Redis durante escrituras concurrentes:** Como máximo puede retrasarse hasta `60s` (el TTL del muro) la visualización de un comentario escrito en el instante exacto del *cache miss*, sin perderse nunca en Cassandra.

### 13. ¿Qué información no pueden afirmar porque no fue medida?
- **Respuesta:**
  - No afirmamos haber medido `100.000 req/s` ni `2–3 millones de usuarios` reales porque todo el laboratorio corre en una única computadora personal.
  - No afirmamos haber medido tiempos de failover automático multi-región ni latencias WAN entre Sudamérica y Europa porque cada motor corre en un único contenedor local.
  - No afirmamos monitorear métricas internas de JVM/WiredTiger en Grafana porque usamos el Compose liviano de la cátedra (`prometheus`, `grafana`, `node-exporter`) instrumentando los 6 adaptadores desde `/metrics` de la API.

### 14. ¿Qué costo operativo agrega mantener seis modelos o productos?
- **Respuesta:**
  - **Costo real experimentado en el TPO:** Seis clientes/drivers distintos en Python (`pymongo`, `neo4j`, `cassandra-driver`, `redis`, `httpx`, `intersystems-irispython`), seis esquemas de autenticación/configuración, seis modos de falla diferentes (que nos obligaron a construir el evaluador de 9 capas del Hito 11) y mayor consumo base de RAM/CPU para mantener todos los contenedores activos.
  - **Por qué se justifica:** En un evento de la escala del Mundial 2030, el costo operativo de gestionar motores especializados (mitigado con contenedores, adaptadores uniformes y monitoreo centralizado en Prometheus/Grafana) es significativamente menor que el riesgo de caída total por forzar un único motor a resolver patrones de acceso incompatibles.

# Guion de Defensa Grupal (20 Minutos) ante la FIFA — Fixture 2030

Este guion organiza la exposición grupal cumpliendo el límite estricto de **20 minutos** (**RF13**, **RNF12** y **Sección 6.2** de la consigna). Prioriza la defensa de las **bases de datos y las decisiones de arquitectura**, utilizando la presentación HTML ([`presentacion.html`](presentacion.html)), Swagger/Postman, clientes nativos y Grafana como medios de demostración.

---

## 1. Distribución del Tiempo y Roles (20 Minutos Totales)

| Bloque | Tiempo | Responsable Sugerido | Contenido y Objetivo Técnico | Recurso en Pantalla |
|---|---|---|---|---|
| **1. Inicio y Problema FIFA** | `00:00 – 02:30` (2,5 min) | **Integrante 1** | Alcance del Mundial 2030 (6 países, 3 continentes, 64 selecciones, 127 partidos, 2–3M usuarios, `<100ms` SLA) y por qué un único motor relacional no escala para patrones de acceso contrapuestos. | [`presentacion.html`](presentacion.html) (Slides 1–2) |
| **2. Arquitectura Políglota (Bloque A: Documental, Grafo y Objetos)** | `02:30 – 07:30` (5,0 min) | **Integrante 1** | Justificación de **MongoDB** (`equipos`/`jugadores`, `IXSCAN`, CP), **Neo4j** (`Partido←Evento←Jugador`, recorrido Cypher en 5,9 ms) e **IRIS** (herencia `Persona→Arbitro/Tecnico`, relación padre-hijo y regla invariante `Partido.AgregarEvento` en partido `Finalizado`). | [`presentacion.html`](presentacion.html) (Slides 3–4) + consulta rápida en Swagger (`GET /equipos/ARG`, `GET /partidos/P-001/eventos`, `GET /partidos-oficiales/P-009`). |
| **3. Arquitectura Políglota (Bloque B: Columnar, Clave-Valor, Series Temporales y Carga)** | `07:30 – 13:30` (6,0 min) | **Integrante 2** | Justificación de **InfluxDB 3** (tags de baja cardinalidad + `DATE_BIN`), **Cassandra** (particionamiento `(codigo_partido, ventana, shard)` + `TIMEUUID`, AP) y **Redis** (sesiones con `noeviction` vs caché). Explicación del cuello de botella del **Hito 12** (fan-out de 12 consultas en Cassandra) y cómo el muro precomputado en Redis redujo `p50` un `88,6%` y CPU de Cassandra un `80%`. | [`presentacion.html`](presentacion.html) (Slides 5–7) + Swagger (`GET /partidos/P-001/comentarios`, `GET /sesiones/S-0001`, `GET /partidos/P-001/estadisticas`). |
| **4. Conectividad por Capas, Observabilidad y Falla Controlada** | `13:30 – 18:00` (4,5 min) | **Integrante 3** | Demostración de la matriz de 9 capas (**Hito 11**), el modelo Pull de **Prometheus** (`15s`) sobre `/metrics` de la API y `node-exporter`, el dashboard **Grafana War Room** (disponibilidad `fixture_db_up`, latencia vs SLA 100ms, RPS y comparación entre las 6 bases) y evidencia de la **falla controlada** (`docker stop` → `503` aislado + alerta → `docker start`). | [`presentacion.html`](presentacion.html) (Slides 8–9) + **Grafana** (`localhost:3000`) y **Prometheus** (`localhost:9090/targets`). |
| **5. Cierre, Límites del Laboratorio y Trade-offs** | `18:00 – 20:00` (2,0 min) | **Integrante 3** (con cierre grupal) | Separación honesta entre lo medido en laboratorio y las proyecciones mundialistas, trade-offs aceptados (complejidad operativa de 6 motores, consistencia eventual de 60s en el muro) y mejoras futuras (Data Mart analítico y exporters dedicados). | [`presentacion.html`](presentacion.html) (Slide 10). |

---

## 2. Guion Detallado Bloque por Bloque

### Bloque 1 — Problema de la FIFA y Decisión General (`00:00 – 02:30`)
- **Idea fuerza:** *«No elegimos seis motores por variedad tecnológica, sino porque el Mundial 2030 combina datos maestros estables, relaciones de grafo, escrituras masivas en ráfagas post-gol, sesiones efímeras, telemetría temporal y actas normativas inmutables.»*
- **Qué destacar:**
  - Mostrar cómo cada requisito del Fixture mapea a un patrón de lectura/escritura distinto.
  - Explicar que la **API REST del Hito 10** actúa como fachada unificada: valida parámetros antes de tocar cualquier base (`400`), traduce errores nativos de los 6 drivers a respuestas uniformes (`503`/`504`) y propaga `X-Request-ID` en logs y headers.

### Bloque 2 — MongoDB, Neo4j e InterSystems IRIS (`02:30 – 07:30`)
- **MongoDB (Hito 4):**
  - *Por qué documental:* `GET /equipos/ARG` recupera la selección completa en un solo documento BSON indexado por `codigo_iso` (`IXSCAN`, `3,5 ms`).
  - *Por qué separamos `equipos` y `jugadores`:* Evita documentos sobredimensionados y permite indexar `{equipo_iso: 1, posicion: 1}`.
- **Neo4j (Hito 5):**
  - *Por qué grafo:* Para recorrer `(Partido)<-[:OCURRE_EN]-(Evento)<-[:PROTAGONIZA]-(Jugador)` y consultar cruces de rivales o jugadores por sede sin *JOINs* costosos (`5,9 ms`, 1.542 nodos y 1.480 relaciones verificadas con `MERGE` idempotente).
- **InterSystems IRIS (Hito 9):**
  - *Por qué objetos/multimodelo:* Las 127 actas oficiales requieren herencia (`Fixture.Persona` → `Arbitro` / `Tecnico`), composición padre-hijo (`Partido` → `EventoPartido`) y la regla encapsulada **`Partido.AgregarEvento`**: si el partido está `"Finalizado"`, el propio objeto rechaza el evento (`REGLA_OK`), exponiéndose hacia la API por proyección SQL parametrizada.

### Bloque 3 — InfluxDB, Cassandra, Redis y Optimización bajo Carga (`07:30 – 13:30`)
- **InfluxDB 3 Core (Hito 8):**
  - *Por qué series temporales:* Ingesta en Line Protocol y agregación temporal con `DATE_BIN` (`10s`, `1m`, `5m`) usando solo tags de baja cardinalidad (`partido_id`, `equipo_id`) para evitar explosión de cardinalidad.
- **Cassandra (Hito 6) + Redis (Hito 7) + Pruebas de Carga (Hito 12):**
  - *Diseño en Cassandra:* Clave de partición compuesta `((codigo_partido, ventana, shard), id_comentario)` con `TIMEUUID DESC`. Los 4 shards por minuto distribuyen las escrituras en picos de gol.
  - *Decisión clave en Redis (Hito 7):* Cambiamos a `noeviction` porque una sesión activa (`sesion:S-0001`) es estado de acceso y no debe desalojarse antes de que venza su TTL de 30 minutos.
  - *Triangulación y optimización del Hito 12:* Con `nodetool proxyhistograms` vimos que una consulta en Cassandra tardaba `0,06 ms`, pero leer el muro hacía **12 consultas por lectura** (`4.800 consultas/s` a `500 ops/s`). Precomputando los últimos 100 comentarios en Redis (`muro:P-001` con `LPUSHX`, `LTRIM 0 99`, `TTL 60s` y lock `SET NX EX 2`), el `p50` cayó de **`14,70 ms` a `1,67 ms` (`-88,6%`)**, el CPU de Cassandra bajó de **`77%` a `15,5%` (`-80%`)** y el throughput máximo subió de **`484` a `6.737 ops/s`**.

### Bloque 4 — Conectividad (Hito 11) y Monitoreo en Vivo (Hito 13) (`13:30 – 18:00`)
- **Conectividad y Readiness (Hito 11):**
  - Mostrar `/health/dependencias` y cómo el evaluador de 9 capas distingue un puerto cerrado de una credencial inválida o una base/keyspace inexistente.
- **Prometheus y Grafana (Hito 13):**
  - Mostrar en `http://localhost:9090/targets` los 3 jobs (`prometheus`, `node-exporter`, `fixture-api`).
  - Mostrar en **Grafana (`http://localhost:3000`)** el dashboard **War Room**:
    1. Panel `fixture_db_up` con las 6 bases en verde (`1`).
    2. Latencia `p95` por debajo de la línea roja del SLA (`100ms`).
    3. Comparación de latencia por motor (Redis `~1 ms` vs MongoDB/Neo4j/IRIS `~3–6 ms` vs InfluxDB/Cassandra `~30–75 ms`).
    4. Demostración de la **prueba de falla controlada**: mostrar cómo al detener Redis (`docker stop fixture2030-redis`), `fixture_db_up{db="redis"}` cae a `0`, `/sesiones/S-0001` devuelve `503`, `/equipos/ARG` sigue en `200 OK`, se activa la alerta `BaseDatosNoSQLNoDisponible`, y al ejecutar `docker start` todo vuelve a verde sin perder datos.

### Bloque 5 — Cierre, Honestidad Experimental y Mejoras (`18:00 – 20:00`)
- **Qué medimos vs qué proyectamos:** Dejar claro que medimos latencias, aislamiento de fallas y el salto de `14×` en throughput en un nodo local, mientras que los `100.000 req/s` y la replicación multi-continente son proyecciones de la arquitectura distribuida diseñada.
- **Qué mejoraríamos en la siguiente iteración:** Separar físicamente Redis sesiones de Redis caché, proyectar los datos operacionales al **Data Mart estrella** diseñado en el Hito 12 para consultas analíticas de la FIFA, y sumar exporters JMX/WiredTiger dedicados por motor.

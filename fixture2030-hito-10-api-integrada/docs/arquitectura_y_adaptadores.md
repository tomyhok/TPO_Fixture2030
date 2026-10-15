# Hito 10 — Arquitectura y Adaptadores

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Arquitectura**, **Adaptadores** y
**Coherencia con el TPO** de la sección 8 del enunciado (RF9, RNF1, RNF5).

---

## 1. Capas

```
Cliente HTTP (Swagger UI, cURL, Postman, app)
   │
   ▼
app/routes/        Contrato HTTP: rutas, métodos, validación de ruta/query/cuerpo,
   │               códigos de estado y headers (X-Cache, Location, Idempotent-Replayed)
   ▼
app/services/      Casos de uso: reglas de negocio, combinación de fuentes
   │               (caché, idempotencia), traducción de resultados a errores de dominio
   ▼
app/adapters/      Un adaptador por producto: conexión, contexto, consulta parametrizada,
   │               conversión al modelo interno y traducción de errores del driver
   ▼
Driver nativo      pymongo · neo4j · cassandra-driver · redis-py · httpx (API v3) · intersystems-irispython
   │
   ▼
Base NoSQL         MongoDB · Neo4j · Cassandra · Redis · InfluxDB 3 · IRIS
```

| Carpeta | Responsabilidad | Qué **no** hace |
|---|---|---|
| `app/routes/` | Declarar el contrato HTTP y delegar en un servicio. Cada función tiene 1 a 5 líneas. | No importa drivers, no arma consultas, no captura excepciones. |
| `app/schemas/` | Modelos Pydantic de request y response: formatos, rangos, enums, `extra="forbid"`. Generan el OpenAPI. | No accede a datos. |
| `app/services/` | Un servicio por módulo. Decide qué fuente consultar, combina fuentes y convierte resultados de negocio en errores (`RecursoNoEncontrado`, `ConflictoEstado`...). | No conoce el driver ni el lenguaje de consulta. |
| `app/adapters/` | Único lugar donde se importan los drivers (RNF5). Expone métodos con nombres del dominio (`leer_muro`, `ficha_partido`). | No conoce HTTP ni códigos de estado. |
| `app/core/` | Errores de la aplicación, request ID, logs, middleware, manejadores de error y ajuste del OpenAPI. | — |
| `app/config/` | Lectura de la configuración desde variables de entorno o `.env` (RNF6). | No contiene valores secretos. |
| `app/dependencias.py` | Composición: crea adaptadores y servicios y los inyecta. Las pruebas unitarias reemplazan los adaptadores por dobles. | — |

### Flujo de una request (ejemplo CU09, publicar comentario)

1. `routes/comentarios.py` valida el código de partido, el cuerpo y el header
   `Idempotency-Key`. Si algo es inválido responde 400 y termina (RNF3).
2. `services/comentarios_service.py` delega en `services/idempotencia.py`,
   que reserva la clave en Redis (`RedisAdapter.reservar_idempotencia`).
3. El servicio pide a `Neo4jAdapter.existe_partido` que confirme el partido.
4. El servicio calcula ventana, shard, período y timeuuid, y llama a
   `CassandraAdapter.publicar`, que ejecuta el BATCH con sentencias preparadas.
5. La idempotencia guarda la respuesta. La ruta devuelve 201 con `Location`.
6. Cada adaptador registra su operación y duración, y el middleware registra
   la request. Todas esas líneas comparten el mismo `request_id`.

## 2. Adaptadores

Todos usan `adapters/base.py::operacion()`. Ese contexto mide la duración,
registra `dependencia`, `operacion`, `resultado` y `duracion_ms`, y traduce las
excepciones del driver con la función `_traducir` propia de cada adaptador:

* excepción de **disponibilidad** (conexión rechazada, sin host, autenticación) → `DependenciaNoDisponible` (503);
* excepción de **tiempo** (timeout de conexión u operación) → `DependenciaTimeout` (504);
* cualquier otra (error de programación) → se propaga y termina en 500 con el detalle solo en el log.

Los adaptadores crean la conexión de forma **perezosa**: la API arranca aunque
una base esté caída, y se reconecta sola cuando la base vuelve. La evidencia
está en `evidencia/09_dependencia_caida.txt`.

| Adaptador | Conexión | Contexto | Operaciones (patrón del hito de origen) | Conversión | Errores traducidos | Cierre |
|---|---|---|---|---|---|---|
| `MongoAdapter` | `MongoClient` con usuario de `.env`, `serverSelectionTimeoutMS`, `connectTimeoutMS`, `socketTimeoutMS` | database `MONGO_DATABASE` | `find_one` por `_id`, `find` filtrado por `confederacion`/`grupo` ordenado por `ranking_fifa` con `skip`/`limit`, `find` por `codigo_equipo`+`posicion` (índices del Hito 4) | Proyección explícita por caso. `_id` del jugador → `id_jugador` | `ConnectionFailure`, `OperationFailure` → 503. `NetworkTimeout`, `ExecutionTimeout` → 504 | `close()` al apagar |
| `Neo4jAdapter` | `GraphDatabase.driver` con `connection_timeout` y `connection_acquisition_timeout` | sesión `READ_ACCESS` sobre `NEO4J_DATABASE` | Cypher fijo y parametrizado (`$codigo`, `$limit`): ficha (profundidad 1), eventos con protagonista (profundidad 2, `LIMIT`), rivales (`LIMIT`). Auto-commit con `Query(timeout=...)`, sin reintentos ocultos | Nodos y relaciones → diccionarios. `local`/`visitante` según `DISPUTA.condicion`. `null` = partido inexistente, `[]` = sin eventos | `ServiceUnavailable`, `SessionExpired`, `AuthError` → 503. Código `TransactionTimedOut*` → 504 | `driver.close()` |
| `CassandraAdapter` | `Cluster` con `ExecutionProfile` (`DCAwareRoundRobinPolicy`, `request_timeout`, `dict_factory`), `connect_timeout` | keyspace `CASSANDRA_KEYSPACE` | Sentencias preparadas. Muro: 4 SELECT en paralelo, uno por shard, con la clave de partición completa y `LIMIT n+1`; cursor = `id_comentario < ?`. Alta: BATCH logged en `comentarios_por_partido` y `comentarios_por_usuario` | Combina los 4 shards por timeuuid descendente. `timeuuid` → string, `creado_en` → UTC | `NoHostAvailable`, `Unavailable` → 503. `OperationTimedOut`, `Read/WriteTimeout` → 504 | `cluster.shutdown()` |
| `RedisAdapter` | `redis.Redis` con `socket_connect_timeout`, `socket_timeout`, **sin reintentos** (`Retry(NoBackoff(), 0)`) | db `REDIS_DB` | `HMGET`+`TTL` en pipeline (sesión), `DEL`, `GET`/`SET EX` (caché), `SET NX EX` / `GET` / `SET XX KEEPTTL` / `DEL` (idempotencia) | Solo los campos públicos de la sesión. `TTL -2` = inexistente | `ConnectionError` (incluye auth) → 503. `TimeoutError` → 504 | `close()` |
| `InfluxAdapter` | `httpx.Client` con `Timeout(operacion, connect=conexion)` y token Bearer (de `.env` o del archivo del Hito 8) | database `INFLUX_DATABASE` en cada consulta | `POST /api/v3/query_sql` con SQL fijo y `params` (`$partido`, `$equipo`, `$desde`, `$hasta`, `$tope`). `date_bin` con intervalo de una lista cerrada | Instantes → UTC. Posesión redondeada a 2 decimales | `TransportError` y HTTP ≠ 200 (401, 404 database) → 503. `TimeoutException` → 504. `[]` con 200 = sin puntos | `close()` |
| `IrisAdapter` | Native API (`iris.connect` con `timeout`) con el usuario `fixture_api` y el rol mínimo `FixtureAPI` | namespace `IRIS_NAMESPACE` | `classMethodValue("Fixture.API", ...)`: `ObtenerActa`, `CambiarEstado`, `RegistrarEvento`. Cada llamada corre en un hilo con límite de espera, porque el cliente no tiene timeout por operación | JSON de la fachada → dict. `detalle_interno` se registra en el log y se descarta | `RuntimeError` del cliente (link caído, `<PROTECT>`) → 503. Límite de espera vencido → 504 | La conexión se descarta ante cualquier error y al apagar |

### Por qué IRIS usa una clase fachada

El Hito 9 encapsuló las reglas en el modelo de objetos (`VALUELIST`,
`MINVAL`/`MAXVAL`, `%OnBeforeSave`). Esas reglas se ejecutan al hacer `%Save()`
sobre objetos, y no con un `INSERT` SQL. `Fixture.API` (`iris/Fixture.API.cls`)
trabaja con objetos: abre por índice único, navega `Arbitro` y `Eventos` y
guarda con `%Save()`. La API la invoca por la Native API. Así las validaciones
siguen dentro de IRIS y el adaptador solo traduce resultados de negocio
(`NO_ENCONTRADO`, `TRANSICION_INVALIDA`, `PARTIDO_FINALIZADO`). El usuario de
la API tiene un rol propio con solo `%DB_USER` y `%Native_ClassExecution:U`.

### Combinación de fuentes justificada

| Caso | Fuentes | Justificación |
|---|---|---|
| CU05 ficha del partido | Redis + Neo4j | Es la lectura más frecuente (≈ 20.000/s en el pico, Hito 7 PA3) y la ficha cambia de 10 a 20 veces por partido. Se usa cache-aside con TTL de 300 s. Si Redis cae la respuesta se degrada a lectura directa (`X-Cache: BYPASS`). Si Neo4j cae pero la caché está vigente, se sigue respondiendo. |
| CU09 publicar comentario | Redis + Neo4j + Cassandra | Neo4j es la fuente de verdad de qué partidos existen. Redis guarda la clave de idempotencia con TTL (dato temporal, como en el Hito 7). Cassandra recibe la escritura masiva. |
| CU15 evento del acta | Redis + IRIS | Un reintento no debe registrar dos veces el mismo gol. La clave se guarda en Redis por el mismo motivo que en CU09. |

Ninguna otra ruta mezcla fuentes: cada módulo responde con su propio modelo.

## 3. Coherencia con el TPO

| Módulo | Hito | Qué reutiliza la API | Qué se agregó en el Hito 10 |
|---|---|---|---|
| MongoDB | 4 | Colecciones `equipos` y `jugadores`, índices `idx_ranking`, `idx_confederacion`, `idx_grupo`, `idx_equipo_posicion`, consultas 1–4 de `02-consultas.js` | Nada en la base |
| Neo4j | 5 | Modelo `Equipo`–`DISPUTA`–`Partido`–`SE_JUEGA_EN`–`Sede`, `Evento`–`CORRESPONDE_A`, `Jugador`–`PROTAGONIZA`. Restricciones de unicidad. Consulta de rivales | Nada en la base |
| Cassandra | 6 | Tablas `comentarios_por_partido` (clave `(id_partido, ventana, shard)`) y `comentarios_por_usuario`, bucket de 1 minuto, `shard = crc32(id_usuario) % 4`, timeuuid | Nada en la base |
| Redis | 7 | `sesion:<id>` (Hash + TTL), `cache:partido:<codigo>` (String JSON + TTL 300 s) | Familia `idem:<operacion>:<clave>` (TTL 24 h) |
| InfluxDB | 8 | Tabla `estadisticas_partido`, tags `partido_id`/`equipo_id`, agregaciones AVG/MAX justificadas | Series de `P-001` y `P-002` con códigos homologados (`scripts/datos/`) |
| IRIS | 9 | Clases `Fixture.Partido`, `Fixture.Evento`, `Fixture.Arbitro` y sus validaciones | Propiedad `Codigo` + índice único y fachada `Fixture.API` |

Además, en el `docker-compose.yml` raíz y en el del módulo IRIS se cambió
`ISC_DATA_DIRECTORY` de `/durable` a `/durable/iris`, que es lo que recomienda
InterSystems. Con `/durable`, IRIS exige un directorio vacío y no reiniciaba
sobre un bind mount que ya tenía datos.

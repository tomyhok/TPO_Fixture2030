# Diagnóstico de fallas y comportamiento de la API

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Cubre RF17, RF18, RF20, RF21, RNF10, RNF12 y las secciones 5.7 y 6 ("No se
deberán ocultar fallas de dependencia devolviendo 200"). Todas las fallas se
provocaron de forma **controlada y reversible**: se cambió una variable de
entorno de un proceso o se detuvo y reinició un contenedor. Nunca se usó
`docker compose down -v`, `docker rm` ni ningún borrado.

## 1. Fallo controlado: MongoDB detenido (5.7, RF21)

Script: [`../scripts/fallo_controlado.sh`](../scripts/fallo_controlado.sh).
Evidencia: [`evidencia/fallo_controlado_mongodb.txt`](evidencia/fallo_controlado_mongodb.txt)
(corrida `h11-fallo-*`, 2026-10-17 00:33 UTC).

| Ítem exigido | Registro |
|---|---|
| **Condición inicial** | `fixture2030-mongodb` running (restart policy `always`), volumen `fixture_mongodb_data` creado el 2026-09-25. Datos: `equipos=64 jugadores=1472`. `GET /equipos/ARG` → 200 en 7,6 ms; `/health/dependencias` → las seis `up` |
| **Cambio aplicado** | `docker stop fixture2030-mongodb` (1 s). El contenedor y el volumen se conservan |
| **Prueba ejecutada** | Diagnóstico por capas de MongoDB (modo completo) + rutas de la API con `X-Request-ID` + líneas de log |
| **Diagnóstico por capas** | Contenedor WARN `exited; puertos publicados: ninguno`. **TCP FAIL**: `connection refused tras 2057 ms`. Protocolo a lectura: SKIP "no evaluada: falló la capa 'tcp'". Matriz: **no disponible**, columna API FAIL |
| **Respuesta de la API** | `GET /equipos/ARG` → **503** `DEPENDENCIA_NO_DISPONIBLE`, `detalles: [{"dependencia":"mongodb"}]`. `GET /partidos/P-001/eventos` → **200** (Neo4j, sin impacto). `GET /health/ready` → **200** `listo=true, estado=degraded, no_disponibles=["mongodb"]`. `GET /health/dependencias?refrescar=true` → `mongodb=down (DEPENDENCIA_NO_DISPONIBLE)`, las demás `up`. `GET /health` → **503** `mongodb: caida` |
| **Mensaje de log** | `WARNING [fixture2030.adaptador] request_id=h11-fallo-…-03 dependencia=mongodb operacion=equipos.find_one resultado=DEPENDENCIA_NO_DISPONIBLE:ServerSelectionTimeoutError duracion_ms=…` seguido de `[fixture2030.acceso] … ruta=/equipos/ARG estado=503` |
| **Tiempo de espera** | 2,06 s para la ruta (límite `TIMEOUT_CONEXION_S=2`, `serverSelectionTimeoutMS`). Ninguna request quedó bloqueada |
| **Recuperación** | `docker start fixture2030-mongodb`; el protocolo respondió **2375 ms** después. La API se reconectó sola, sin reinicio |
| **Resultado después** | Diagnóstico de MongoDB: **disponible** (8/8 capas OK, API OK). `GET /equipos/ARG` → 200 en 5,8 ms; `/health/dependencias` → `mongodb=up` |
| **Datos y volúmenes conservados** | Antes y después: `equipos=64 jugadores=1472`, mismo volumen `fixture_mongodb_data` con la misma fecha de creación |

Observaciones:

* **La falla queda aislada en su módulo.** Las rutas de Neo4j siguieron respondiendo 200 y readiness siguió en 200 con la fuente afectada identificada.
* **El TTL del chequeo profundo tiene un efecto visible.** Readiness se calcula sobre un diagnóstico reutilizado hasta 10 s (`HEALTH_CACHE_TTL_S`). Justo después de la recuperación, readiness todavía informó `degraded` durante unos segundos y `refrescar=true` mostró `up`. Es el costo aceptado para no consultar las seis bases en cada sondeo (ver [`health_readiness.md`](health_readiness.md)).

## 2. Escenarios de configuración y corrección (5.7, RF20)

Script: [`../scripts/escenarios_configuracion.sh`](../scripts/escenarios_configuracion.sh) parte A.
Evidencia: [`evidencia/escenarios_configuracion.txt`](evidencia/escenarios_configuracion.txt).
Cada caso cambia **una** variable solo para el proceso del diagnóstico. A7
repite la evaluación con la configuración original.

| Caso | Hipótesis | Prueba | Resultado observado | Siguiente paso que propone el diagnóstico |
|---|---|---|---|---|
| A1 host incorrecto (`MONGO_HOST=mongodb`) | Se usó el nombre de servicio Docker desde la notebook | Resolución | **FAIL resolución**: `getaddrinfo failed` (2,8 s); el resto en SKIP | Desde la notebook usar `127.0.0.1`; el nombre de servicio solo sirve dentro de la red de Compose |
| A2 puerto equivocado (`NEO4J_URI=bolt://127.0.0.1:7474`) | El puerto es de otro protocolo | TCP + handshake Bolt | TCP OK; **FAIL protocolo**: `respondió HTTP/1.1 400 Bad Request, no Bolt` | Corregir el puerto de `NEO4J_URI` (7687) |
| A3 puerto no publicado (`REDIS_PORT=6380`) | Nadie escucha en ese puerto | TCP | **FAIL TCP**: `connection refused tras 2042 ms` | `docker port`; verificar `REDIS_PORT` contra el compose |
| A4a keyspace inexistente | El contexto no existe | Metadata del driver | Protocolo, AuthN y AuthZ OK; **FAIL contexto**: keyspace inexistente (lista los existentes) | Corregir `CASSANDRA_KEYSPACE` o ejecutar `01-keyspace.cql` |
| A4b database de Neo4j inexistente | El contexto no existe | `db.info()` | **FAIL contexto**: `Neo.ClientError.Database.DatabaseNotFound` | Corregir `NEO4J_DATABASE` |
| A4c database de InfluxDB inexistente | El contexto no existe | Listado de databases | **FAIL contexto**: inexistente (existen `_internal`, `fixture2030`) | Corregir `INFLUX_DATABASE` |
| A4d database de MongoDB inexistente | MongoDB no da error, devuelve vacío | Colecciones esperadas | **FAIL contexto**: sin `equipos` ni `jugadores` | Corregir `MONGO_DATABASE` / ejecutar la carga del Hito 4 |
| A4e namespace de IRIS inexistente | IRIS responde "Access Denied" | Login + diferencial | Protocolo OK; **AuthN OK** (verificada en `USER`); **FAIL contexto**: `%SYS.Namespace.Exists = 0` | Corregir `IRIS_NAMESPACE` |
| A5 credencial inválida (`MONGO_PASSWORD`) | La contraseña no coincide | `connectionStatus` | **FAIL autenticación**: `AuthenticationFailed, código 18` | Comparar el `.env` con el compose, sin publicar el valor |
| A6 timeout demasiado bajo (`TIMEOUT_OPERACION_S=0.001`, InfluxDB) | El límite es menor que el tiempo de respuesta | Capas HTTP | Las primeras capas pasan (responden en menos de 1 ms); **FAIL lectura: timeout** en la consulta más pesada | Usar un timeout realista; si persiste, revisar la carga |
| A7 corrección | — | Modo nativo completo | Los seis **disponible** | — |

La misma prueba cambió de estado al corregir la variable: ese es el registro de
RF20 para cada caso. En el fallo controlado (§1), el cambio de estado se debió a
la recuperación del servicio.

## 3. Comportamiento de la API ante cada tipo de falla (RF17, RF18)

Script: `escenarios_configuracion.sh` parte B. Levanta **instancias temporales**
de la API, con configuración errónea por variables de entorno, en los puertos
8002 y 8003; prueba sus rutas y las detiene. La API principal (8000) no se toca.

**B1 — API en 8002 con todas las dependencias mal configuradas.** Configuración:
`MONGO_DATABASE`, `NEO4J_DATABASE`, `CASSANDRA_KEYSPACE` e `INFLUX_DATABASE`
inexistentes, `REDIS_PORT=6380` e `IRIS_PORT=1973`. IRIS se rompe por puerto y
no por credencial, para no provocar logins fallidos.

| Falla | Ruta | Respuesta | Log del adaptador | Espera |
|---|---|---|---|---|
| Contexto inexistente (MongoDB) | `GET /equipos/ARG` | **503** `DEPENDENCIA_NO_DISPONIBLE (mongodb)` | `resultado=DEPENDENCIA_NO_DISPONIBLE:_ContextoIncompleto` | 7 ms |
| Contexto inexistente (Neo4j) | `GET /partidos/P-001/eventos` | **503** `(neo4j)` | `…:ClientError` (`DatabaseNotFound`) | 10 ms |
| Contexto inexistente (Cassandra) | `GET /partidos/P-001/comentarios?ventana=…` | **503** `(cassandra)` | `…:NoHostAvailable` | 1,4 s |
| Puerto no publicado (Redis) | `GET /sesiones/S-0001` | **504** `DEPENDENCIA_TIMEOUT (redis)` | `DEPENDENCIA_TIMEOUT:TimeoutError` | 2,0 s (rechazo de Windows ≈ timeout) |
| Contexto inexistente (InfluxDB) | `GET /partidos/P-001/estadisticas?…` | **503** `(influxdb)` | `…:_RespuestaInvalida` (HTTP 404 de InfluxDB) | 31 ms |
| Puerto no publicado (IRIS) | `GET /partidos-oficiales/P-001` | **503** `(iris)` | `…:RuntimeError` (`COMMUNICATION LINK ERROR`) | 2,1 s |
| Ninguna fuente disponible | `GET /health/ready` | **503** `listo=false, estado=down` | `diagnostico estado=down mongodb=down …` | 2,1 s (chequeos en paralelo) |
| Validación | `GET /equipos/arg`, intervalo invertido | **400** (no consulta ninguna base) | sin línea de adaptador | menos de 5 ms |

**B2 — API en 8003 con `TIMEOUT_OPERACION_S=0.001` (dependencia "lenta").**
`GET /partidos/P-001/estadisticas` → **504** `DEPENDENCIA_TIMEOUT (influxdb)`.
Las demás rutas respondieron dentro de 1 ms. El resultado es **intermitente**: en
otra corrida también cortó la ventana sin puntos o el primer `PING` de Redis.
Un timeout irreal produce fallas aleatorias, que es justo lo que hay que evitar.

**Cómo diferencia la API cada caso (RF18):**

| Caso | HTTP | `error.codigo` | ¿Identifica la dependencia? |
|---|---|---|---|
| Ausencia válida | 404 | `RECURSO_NO_ENCONTRADO` / `SESION_NO_VIGENTE` | No corresponde (la fuente respondió) |
| Respuesta vacía válida | 200 | — (lista vacía) | — |
| Error de validación | 400 | `VALIDACION` (con `detalles[].campo`) | No se consulta ninguna fuente |
| Dependencia no disponible (caída, rechazo, credencial, contexto inexistente) | 503 | `DEPENDENCIA_NO_DISPONIBLE` | Sí: `detalles[].dependencia` |
| Timeout | 504 | `DEPENDENCIA_TIMEOUT` | Sí |
| Error interno | 500 | `ERROR_INTERNO` (detalle solo en el log, con el request ID) | No se expone al consumidor |

**Degradación (RNF12).** No hay reintentos ocultos: Redis usa `Retry(NoBackoff(), 0)`,
Neo4j trabaja en auto-commit sin `execute_read` con reintentos y no hay bucles
de reintento propios. Cada espera está acotada por los timeouts de conexión y
operación. IRIS además tiene un límite por hilo porque su cliente no corta solo.
Ninguna falla de dependencia devuelve 200, salvo la degradación documentada del
Hito 10: con la caché de Redis caída, la ficha del partido se lee de Neo4j con
`X-Cache: BYPASS`.

## 4. Hallazgos y cambios realizados

| # | Hallazgo (hipótesis → prueba → resultado) | Cambio | Estado |
|---|---|---|---|
| 1 | Con `NEO4J_DATABASE` inexistente, ¿la API responde 503? → API temporal con `NEO4J_DATABASE=noexiste` → `ClientError` sin traducir: **500 ERROR_INTERNO** | `neo4j_adapter._traducir` mapea `Neo.ClientError.Database.DatabaseNotFound` a `DependenciaNoDisponible`; prueba `test_neo4j_database_inexistente_es_dependencia_no_disponible` | Corregido: 503 (B1) |
| 2 | Con `MONGO_DATABASE` inexistente, ¿la API lo detecta? → API temporal en 8002 → `GET /equipos/ARG` = **404 "No existe la selección"**: ausencia falsa (MongoDB devuelve vacío sin error) | `mongo_adapter` verifica una sola vez que estén las colecciones del módulo antes de la primera operación (y siempre en `ping`); pruebas `test_mongo_database_incorrecta_…` y `test_mongo_contexto_se_verifica_una_sola_vez` | Corregido: 503 (B1) |
| 3 | ¿Por qué Redis detenido daba 504 y no 503 en el Hito 10? → `connect()` a un puerto cerrado con límites de 5 s y 1,5 s → Windows tarda **~2,05 s** en informar el rechazo | `TCP_TIMEOUT_S=3` en el diagnóstico; documentado. La API conserva `TIMEOUT_CONEXION_S=2`: subirlo demoraría todas las caídas reales | Documentado (ver topología §3) |
| 4 | ¿IRIS distingue credencial de namespace? → login con un namespace inexistente → **"Access Denied"**, igual que con contraseña inválida | Diagnóstico diferencial: login en `IRIS_NAMESPACE_ALTERNATIVO` + `%SYS.Namespace.Exists` | Implementado en el diagnóstico |
| 5 | ¿`iris.connect(timeout=…)` corta solo? → conexión al puerto 52773 → **se cuelga** | El diagnóstico usa `con_limite()` (hilo daemon). El adaptador de la API ya limitaba con `ThreadPoolExecutor` | Confirmado y documentado |
| 6 | ¿Cassandra informa el keyspace inexistente como tal? → `connect("noexiste")` → `NoHostAvailable`, igual que una red caída | El diagnóstico conecta sin keyspace y consulta la metadata | Implementado en el diagnóstico |
| 7 | ¿El primer chequeo profundo es representativo? → `/health/dependencias` justo después de arrancar la API → Cassandra `degraded/LATENCIA_ALTA` (1436 ms) por la apertura de la sesión del driver; el segundo chequeo dio 9 ms | Documentado en [`health_readiness.md`](health_readiness.md) | Observación para el Hito 12 |
| 8 | ¿Los secretos se pueden ocultar por valor? → la contraseña de Neo4j coincide con un identificador público (nombre de base) y figura en `docker-compose.yml` | El redactor no la oculta por valor para no tapar el contexto; se informa como "no verificable" | Limitación (ver [`limitaciones_y_coherencia.md`](limitaciones_y_coherencia.md)) |

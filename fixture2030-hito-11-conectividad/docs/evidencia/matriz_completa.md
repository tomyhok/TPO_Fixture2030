# Matriz de conectividad — modo completo

| Campo | Valor |
|---|---|
| etiqueta | modo completo |
| inicio_utc | 2026-10-17T00:33:10Z |
| commit | db0f5fc (hito10, con cambios sin commitear) |
| origen | notebook Windows 11 (Git Bash); 127.0.0.1 = puertos publicados por Docker |
| python | 3.12.10 |
| drivers | pymongo 4.19.0, neo4j 6.4.1, cassandra-driver 3.30.1, redis 8.1.0, intersystems-irispython 5.4.1 |
| configuracion | fixture2030-hito-10-api-integrada/.env |
| modo | completo |
| productos | mongodb, neo4j, cassandra, redis, influxdb, iris |
| capas | autenticacion, autorizacion, configuracion, contenedor, contexto, lectura, portal_http, protocolo, resolucion, sonda, tcp, api |
| timeouts_s | tcp=3 conexion=2 operacion=5 api=15 |
| fin_utc | 2026-10-17T00:33:19Z |
| duracion_s | 8.5 |

## Matriz por producto

| Producto | Estado | Cfg | DNS | TCP | Prot | AuthN | AuthZ | Ctx | Lect | Sondas | API | Lectura (ms) | Diagnóstico |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mongodb | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 3.5 | todas las capas ejecutadas terminaron OK |
| neo4j | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 4/4 | OK | 5.9 | todas las capas ejecutadas terminaron OK |
| cassandra | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 4/4 | OK | 77.2 | todas las capas ejecutadas terminaron OK |
| redis | **disponible** | OK | OK | OK | OK | OK | OK | OK | WARN | 2/2 | OK | 1.2 | observación: EXISTS/TYPE/PTTL: 'sesion:S-0001' ausente o expirada: EXISTS 0, PTTL -2 |
| influxdb | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 34.2 | todas las capas ejecutadas terminaron OK |
| iris | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 3.3 | todas las capas ejecutadas terminaron OK |

## Resultados

| Instante (UTC) | Producto | Capa | Prueba | Estado | ms | Destino | Detalle |
|---|---|---|---|---|---|---|---|
| 2026-10-17T00:33:10Z | mongodb | configuracion | variables | OK | 0.1 | `(configuración)` | MONGO_HOST=127.0.0.1; MONGO_PORT=27017; MONGO_USER=admin; MONGO_PASSWORD (definida, oculta); MONGO_AUTH_DB=admin; MONGO_DATABASE=fixture2030 [origen: archivo fixture2030-hito-10-api-integrada/.env] |
| 2026-10-17T00:33:10Z | mongodb | contenedor | docker inspect | OK | 131.4 | `fixture2030-mongodb` | fixture2030-mongodb: running; puertos publicados: 27017/tcp -> 0.0.0.0:27017. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:10Z | mongodb | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:27017` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:10Z | mongodb | tcp | connect() | OK | 1.2 | `127.0.0.1:27017` | 127.0.0.1:27017 listener aceptó la conexión |
| 2026-10-17T00:33:11Z | mongodb | protocolo | hello (sin credenciales) | OK | 6.1 | `127.0.0.1:27017 database=fixture2030` | primario=True, wire=21, MongoDB 7.0.43 |
| 2026-10-17T00:33:11Z | mongodb | autenticacion | connectionStatus | OK | 30.8 | `127.0.0.1:27017 database=fixture2030` | autenticado como admin@admin (roles: root) |
| 2026-10-17T00:33:11Z | mongodb | autorizacion | listCollections fixture2030 | OK | 1.4 | `127.0.0.1:27017 database=fixture2030` | permitido en 'fixture2030' (2 colecciones) |
| 2026-10-17T00:33:11Z | mongodb | contexto | colecciones esperadas | OK | 0.0 | `127.0.0.1:27017 database=fixture2030` | database 'fixture2030' con las colecciones del módulo: equipos, jugadores |
| 2026-10-17T00:33:11Z | mongodb | lectura | find_one + count_documents | OK | 3.5 | `127.0.0.1:27017 database=fixture2030` | equipos.find_one(_id='ARG') -> Argentina (grupo A); jugadores.count_documents(codigo_equipo='ARG', limit=100) = 23 |
| 2026-10-17T00:33:11Z | mongodb | sonda | documento inexistente | OK | 1.9 | `127.0.0.1:27017 database=fixture2030` | equipos.find_one(_id='ZZZ') -> None: ausencia válida, no es error |
| 2026-10-17T00:33:11Z | mongodb | sonda | colección inexistente | OK | 1.7 | `127.0.0.1:27017 database=fixture2030` | fixture2030.coleccion_inexistente_h11.find_one() -> None: MongoDB no da error; la API lo detecta en /health/dependencias verificando las colecciones |
| 2026-10-17T00:33:11Z | mongodb | sonda | database inexistente | OK | 1.3 | `127.0.0.1:27017 database=fixture2030` | fixture2030_inexistente_h11.listCollections -> []: lista vacía sin error (por eso la capa de contexto verifica colecciones) |
| 2026-10-17T00:33:11Z | neo4j | configuracion | variables | OK | 0.0 | `(configuración)` | NEO4J_URI=bolt://127.0.0.1:7687; NEO4J_HTTP_URL=http://127.0.0.1:7474; NEO4J_USER=neo4j; NEO4J_PASSWORD (definida, oculta); NEO4J_DATABASE=neo4j [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-17T00:33:11Z | neo4j | contenedor | docker inspect | OK | 127.9 | `fixture2030-neo4j` | fixture2030-neo4j: running; puertos publicados: 7474/tcp -> 0.0.0.0:7474, 7687/tcp -> 0.0.0.0:7687. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:11Z | neo4j | portal_http | GET Browser/discovery | OK | 44.6 | `http://127.0.0.1:7474` | HTTP 200: Neo4j 2026.07.1 community; anuncia bolt_direct=bolt://127.0.0.1:7687. La API no usa este puerto: no prueba Bolt |
| 2026-10-17T00:33:11Z | neo4j | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:7687` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:11Z | neo4j | tcp | connect() | OK | 25.8 | `127.0.0.1:7687` | 127.0.0.1:7687 listener aceptó la conexión |
| 2026-10-17T00:33:11Z | neo4j | protocolo | handshake Bolt | OK | 18.2 | `bolt://127.0.0.1:7687 database=neo4j` | versión Bolt 5.8 negociada (magic 0x6060B017) |
| 2026-10-17T00:33:11Z | neo4j | autenticacion | verify_authentication | OK | 8.1 | `bolt://127.0.0.1:7687 database=neo4j` | usuario 'neo4j' autenticado por Bolt |
| 2026-10-17T00:33:11Z | neo4j | autorizacion | SHOW CURRENT USER | OK | 6.7 | `bolt://127.0.0.1:7687 database=neo4j` | identidad 'neo4j' reconocida; roles=null (Community: sin RBAC, toda identidad autenticada puede leer) |
| 2026-10-17T00:33:11Z | neo4j | contexto | db.info() en 'neo4j' | OK | 10.1 | `bolt://127.0.0.1:7687 database=neo4j` | database 'neo4j' seleccionada; etiquetas: Equipo, Jugador, Sede, Partido, Evento |
| 2026-10-17T00:33:11Z | neo4j | lectura | MATCH parametrizado | OK | 5.9 | `bolt://127.0.0.1:7687 database=neo4j` | Partido P-001 (2030-06-10): equipos ARG, ESP [Cypher parametrizado, LIMIT 1, timeout de operación] |
| 2026-10-17T00:33:11Z | neo4j | sonda | partido inexistente | OK | 8.2 | `bolt://127.0.0.1:7687 database=neo4j` | partido P-999 -> sin filas: partido inexistente (la API responde 404) |
| 2026-10-17T00:33:11Z | neo4j | sonda | resultado vacío | OK | 7.0 | `bolt://127.0.0.1:7687 database=neo4j` | partido P-002 existe con 0 eventos: resultado vacío válido (la API responde 200 con lista vacía) |
| 2026-10-17T00:33:11Z | neo4j | sonda | database inexistente | OK | 8.6 | `bolt://127.0.0.1:7687 database=neo4j` | database 'noexiste_h11' -> Neo.ClientError.Database.DatabaseNotFound: error de contexto, no de conexión (la API lo traduce a 503) |
| 2026-10-17T00:33:12Z | neo4j | sonda | error de conexión | OK | 1011.0 | `bolt://127.0.0.1:7687 database=neo4j` | bolt://127.0.0.1:65126 sin listener -> ServiceUnavailable: error de conexión, distinto de 'sin filas' |
| 2026-10-17T00:33:12Z | cassandra | configuracion | variables | OK | 0.0 | `(configuración)` | CASSANDRA_HOSTS=127.0.0.1; CASSANDRA_PORT=9042; CASSANDRA_KEYSPACE=fixture2030; CASSANDRA_DC=datacenter1; CASSANDRA_TABLA=comentarios_por_partido [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-17T00:33:12Z | cassandra | contenedor | docker inspect | OK | 131.7 | `fixture2030-cassandra` | fixture2030-cassandra: running (healthy); puertos publicados: 9042/tcp -> 0.0.0.0:9042. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:12Z | cassandra | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:9042` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:12Z | cassandra | tcp | connect() | OK | 0.7 | `127.0.0.1:9042` | 127.0.0.1:9042 listener aceptó la conexión |
| 2026-10-17T00:33:12Z | cassandra | protocolo | frame OPTIONS | OK | 2.1 | `127.0.0.1:9042 keyspace=fixture2030` | OPTIONS -> SUPPORTED: CQL 3.4.7; protocolos 3/v3, 4/v4, 5/v5, 6/v6-beta |
| 2026-10-17T00:33:12Z | cassandra | autenticacion | frame STARTUP | OK | 2.7 | `127.0.0.1:9042 keyspace=fixture2030` | STARTUP -> READY: el servidor no exige autenticación (AllowAllAuthenticator del laboratorio; cualquier cliente que alcance el puerto puede operar) |
| 2026-10-17T00:33:14Z | cassandra | autorizacion | sesión + system.local | OK | 1384.3 | `127.0.0.1:9042 keyspace=fixture2030` | sesión del driver abierta; SELECT system.local permitido: Cassandra 5.0.9, cluster 'Fixture2030_Cassandra', DC 'datacenter1' |
| 2026-10-17T00:33:14Z | cassandra | contexto | metadata keyspace/tabla | OK | 0.0 | `127.0.0.1:9042 keyspace=fixture2030` | keyspace 'fixture2030' ({'class': 'SimpleStrategy', 'replication_factor': '1'}); comentarios_por_partido: partición (id_partido, ventana, shard), clustering (id_comentario); DC 'datacenter1' coincide |
| 2026-10-17T00:33:14Z | cassandra | lectura | SELECT por partición | OK | 77.2 | `127.0.0.1:9042 keyspace=fixture2030` | partición completa (P-001, 203006152015, shard 0..3), LIMIT 5 c/u: 5 filas [2, 3, 0, 0] |
| 2026-10-17T00:33:14Z | cassandra | sonda | tabla inexistente | OK | 15.0 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="table tabla_inexistente_h11 does not -> consulta inválida (respuesta del servidor), no timeout |
| 2026-10-17T00:33:14Z | cassandra | sonda | keyspace inexistente | OK | 15.8 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="keyspace keyspace_inexistente_h11 do -> contexto inexistente informado por el servidor |
| 2026-10-17T00:33:14Z | cassandra | sonda | partición incompleta | OK | 15.2 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="Cannot execute this query as it migh -> el modelo exige la clave de partición completa (sin ALLOW FILTERING) |
| 2026-10-17T00:33:15Z | cassandra | sonda | timeout de conexión | OK | 1014.0 | `127.0.0.1:9042 keyspace=fixture2030` | 10.255.255.1:9042 -> NoHostAvailable(OSError) en 1013 ms: timeout de conexión (sin respuesta del servidor), distinto de InvalidRequest (el servidor respondió) |
| 2026-10-17T00:33:15Z | redis | configuracion | variables | OK | 0.0 | `(configuración)` | REDIS_HOST=127.0.0.1; REDIS_PORT=6379; REDIS_PASSWORD (vacía); REDIS_DB=0; REDIS_CLAVE_PRUEBA=sesion:S-0001 [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-17T00:33:15Z | redis | contenedor | docker inspect | OK | 157.6 | `fixture2030-redis` | fixture2030-redis: running; puertos publicados: 6379/tcp -> 0.0.0.0:6379. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:15Z | redis | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:6379` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:15Z | redis | tcp | connect() | OK | 24.1 | `127.0.0.1:6379` | 127.0.0.1:6379 listener aceptó la conexión |
| 2026-10-17T00:33:15Z | redis | protocolo | PING (RESP crudo) | OK | 3.7 | `127.0.0.1:6379 db=0` | RESP: PING -> +PONG |
| 2026-10-17T00:33:15Z | redis | autenticacion | ACL WHOAMI | OK | 33.7 | `127.0.0.1:6379 db=0` | sin contraseña configurada; el servidor acepta la conexión como 'default' (laboratorio) |
| 2026-10-17T00:33:15Z | redis | autorizacion | DBSIZE | OK | 1.1 | `127.0.0.1:6379 db=0` | permitido: 7 claves en la base lógica |
| 2026-10-17T00:33:15Z | redis | contexto | CLIENT INFO + INFO keyspace | OK | 3.3 | `127.0.0.1:6379 db=0` | Redis 8.10.2; base lógica db=0: 7 claves, 4 con TTL |
| 2026-10-17T00:33:15Z | redis | lectura | EXISTS/TYPE/PTTL | WARN | 1.2 | `127.0.0.1:6379 db=0` | 'sesion:S-0001' ausente o expirada: EXISTS 0, PTTL -2 |
| 2026-10-17T00:33:15Z | redis | sonda | clave ausente | OK | 2.4 | `127.0.0.1:6379 db=0` | EXISTS diag:h11:inexistente:66f40b1f = 0, PTTL = -2: ausencia válida (nil), no es error |
| 2026-10-17T00:33:15Z | redis | sonda | clave expirada | SKIP | 0.0 | `127.0.0.1:6379 db=0` | desactivada (REDIS_SONDA_EXPIRACION=0): escribe una clave diag: de 1,5 s |
| 2026-10-17T00:33:17Z | redis | sonda | Redis no disponible | OK | 2014.5 | `127.0.0.1:6379 db=0` | 127.0.0.1:65137 sin servidor -> TimeoutError en 2011 ms: excepción, distinta de nil (la API responde 503/504, nunca 404). En Windows el rechazo en 127.0.0.1 tarda ~2 s (reintentos de SYN): con TIMEOUT_CONEXION_S=2 la caída se informa como timeout (504). |
| 2026-10-17T00:33:17Z | influxdb | configuracion | variables | OK | 0.0 | `(configuración)` | INFLUX_URL=http://127.0.0.1:8181; INFLUX_DATABASE=fixture2030; INFLUX_TOKEN (vacía); INFLUX_TOKEN_FILE=../fixture2030-influxDB/.influxdb3-token [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-17T00:33:17Z | influxdb | configuracion | origen del token | OK | - | `http://127.0.0.1:8181 database=fixture2030` | token leído de archivo fixture2030-influxDB/.influxdb3-token (valor oculto) |
| 2026-10-17T00:33:18Z | influxdb | contenedor | docker inspect | OK | 147.9 | `fixture2030-influxdb` | fixture2030-influxdb: running; puertos publicados: 8181/tcp -> 0.0.0.0:8181. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:18Z | influxdb | resolucion | getaddrinfo | OK | 0.1 | `127.0.0.1:8181` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:18Z | influxdb | tcp | connect() | OK | 19.2 | `127.0.0.1:8181` | 127.0.0.1:8181 listener aceptó la conexión |
| 2026-10-17T00:33:18Z | influxdb | protocolo | GET /health (sin token) | OK | 17.4 | `http://127.0.0.1:8181 database=fixture2030` | sin token -> 401: el servicio HTTP responde y exige token también en /health (InfluxDB 3 Core con autorización activa) |
| 2026-10-17T00:33:18Z | influxdb | autenticacion | GET /health (con token) | OK | 3.4 | `http://127.0.0.1:8181 database=fixture2030` | con token -> 200 OK (token de archivo fixture2030-influxDB/.influxdb3-token) |
| 2026-10-17T00:33:18Z | influxdb | autorizacion | listar databases | OK | 2.7 | `http://127.0.0.1:8181 database=fixture2030` | listado de databases permitido: _internal, fixture2030 |
| 2026-10-17T00:33:18Z | influxdb | contexto | database + tabla | OK | 5.3 | `http://127.0.0.1:8181 database=fixture2030` | database 'fixture2030' con la tabla 'estadisticas_partido' |
| 2026-10-17T00:33:18Z | influxdb | lectura | COUNT acotado por tiempo | OK | 34.2 | `http://127.0.0.1:8181 database=fixture2030` | COUNT(*) = 1800 en partido P-001, [2030-06-10T20:00:00Z, 2030-06-10T20:15:00Z) (primero 2030-06-10T20:00:00, último 2030-06-10T20:14:59) |
| 2026-10-17T00:33:18Z | influxdb | lectura | agregación date_bin | OK | 21.9 | `http://127.0.0.1:8181 database=fixture2030` | date_bin(5 min) + AVG(posesion_pct): 3 bloques [50.0, 50.0, 50.0] |
| 2026-10-17T00:33:18Z | influxdb | sonda | token inválido | OK | 23.5 | `http://127.0.0.1:8181 database=fixture2030` | token inválido -> HTTP 401: servicio accesible, autorización rechazada (no es caída) |
| 2026-10-17T00:33:18Z | influxdb | sonda | database inexistente | OK | 2.8 | `http://127.0.0.1:8181 database=fixture2030` | database inexistente -> HTTP 404 {'error': 'query error: database not found: fixture2030_inexistente_h1: error de contexto |
| 2026-10-17T00:33:18Z | influxdb | sonda | ventana sin puntos | OK | 41.3 | `http://127.0.0.1:8181 database=fixture2030` | ventana 2031-01-01 sin datos -> HTTP 200, COUNT(*) = 0: ausencia de puntos válida (la API responde 200 con series vacías) |
| 2026-10-17T00:33:18Z | iris | configuracion | variables | OK | 0.0 | `(configuración)` | IRIS_HOST=127.0.0.1; IRIS_PORT=1972; IRIS_PORTAL_URL=http://127.0.0.1:52773/csp/sys/UtilHome.csp; IRIS_NAMESPACE=USER; IRIS_USER=fixture_api; IRIS_PASSWORD (definida, oculta) [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-17T00:33:18Z | iris | contenedor | docker inspect | OK | 167.5 | `fixture2030-iris` | fixture2030-iris: running (healthy); puertos publicados: 1972/tcp -> 0.0.0.0:1972, 52773/tcp -> 0.0.0.0:52773. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-17T00:33:18Z | iris | portal_http | GET Management Portal | OK | 6.7 | `http://127.0.0.1:52773/csp/sys/UtilHome.csp` | HTTP 200: el Management Portal responde. La API no usa este puerto: no prueba el Superserver |
| 2026-10-17T00:33:18Z | iris | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:1972` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-17T00:33:18Z | iris | tcp | connect() | OK | 24.1 | `127.0.0.1:1972` | 127.0.0.1:1972 listener aceptó la conexión |
| 2026-10-17T00:33:18Z | iris | protocolo | handshake Superserver | OK | 63.6 | `127.0.0.1:1972 namespace=USER` | el Superserver completó el handshake |
| 2026-10-17T00:33:18Z | iris | autenticacion | login en USER | OK | 63.6 | `127.0.0.1:1972 namespace=USER` | usuario 'fixture_api' aceptado en el namespace 'USER' |
| 2026-10-17T00:33:18Z | iris | autorizacion | %SYSTEM.Version.GetNumber | OK | 2.1 | `127.0.0.1:1972 namespace=USER` | Native API puede ejecutar métodos de clase: IRIS 2026.2 |
| 2026-10-17T00:33:18Z | iris | contexto | namespace + clase | OK | 3.7 | `127.0.0.1:1972 namespace=USER` | namespace activo 'USER'; clase Fixture.API compilada |
| 2026-10-17T00:33:18Z | iris | lectura | ObtenerActa | OK | 3.3 | `127.0.0.1:1972 namespace=USER` | Fixture.API.ObtenerActa('P-001') -> estado 'En Juego', sede 'Estadio Monumental', 1 eventos, árbitro con rango FIFA |
| 2026-10-17T00:33:18Z | iris | sonda | objeto inexistente | OK | 1.6 | `127.0.0.1:1972 namespace=USER` | ObtenerActa('P-999') -> {'ok': 0, 'error': 'NO_ENCONTRADO'}: objeto inexistente es respuesta de negocio (la API responde 404), no falla de conexión |
| 2026-10-17T00:33:18Z | iris | sonda | clase inexistente | OK | 1.7 | `127.0.0.1:1972 namespace=USER` | <CLASS DOES NOT EXIST>XDCall+11^%SYS.DBSRV.1: error de metadato, no de conexión |
| 2026-10-17T00:33:18Z | iris | sonda | namespace incorrecto | OK | 1.3 | `127.0.0.1:1972 namespace=USER` | %SYS.Namespace.Exists('NOEXISTE_H11') = 0: con un namespace inexistente iris.connect devuelve 'Access Denied', igual que una credencial inválida; esta consulta los distingue sin provocar logins fallidos |
| 2026-10-17T00:33:18Z | api | api | liveness | OK | 3.0 | `GET http://127.0.0.1:8000/health/live` | HTTP 200 -> exito / estado=up [no consulta bases] |
| 2026-10-17T00:33:18Z | api | api | readiness | OK | 17.8 | `GET http://127.0.0.1:8000/health/ready` | HTTP 200 -> exito / listo=True estado=up no_disponibles=[] [diagnóstico reutilizado (TTL)] |
| 2026-10-17T00:33:18Z | api | api | diagnóstico por dependencia | OK | 20.1 | `GET http://127.0.0.1:8000/health/dependencias?refrescar=true` | HTTP 200 -> exito / estado=up mongodb=up neo4j=up cassandra=up redis=up influxdb=up iris=up |
| 2026-10-17T00:33:18Z | api | api | CU01 equipo | OK | 4.9 | `GET http://127.0.0.1:8000/equipos/ARG` | HTTP 200 -> exito / nombre=Argentina |
| 2026-10-17T00:33:18Z | api | api | CU01 equipo inexistente | OK | 22.9 | `GET http://127.0.0.1:8000/equipos/XYZ` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |
| 2026-10-17T00:33:18Z | api | api | CU01 código inválido | OK | 2.9 | `GET http://127.0.0.1:8000/equipos/arg` | HTTP 400 -> error_validacion / VALIDACION [no llega a la base] |
| 2026-10-17T00:33:18Z | api | api | CU03 plantel | OK | 8.6 | `GET http://127.0.0.1:8000/equipos/ARG/jugadores?size=5` | HTTP 200 -> exito / items: 5 |
| 2026-10-17T00:33:18Z | api | api | CU05 ficha de partido | OK | 18.7 | `GET http://127.0.0.1:8000/partidos/P-001` | HTTP 200 -> exito / codigo_partido=P-001 |
| 2026-10-17T00:33:18Z | api | api | CU06 eventos | OK | 10.9 | `GET http://127.0.0.1:8000/partidos/P-001/eventos?limit=5` | HTTP 200 -> exito / eventos: 1 |
| 2026-10-17T00:33:18Z | api | api | CU06 partido sin eventos | OK | 23.4 | `GET http://127.0.0.1:8000/partidos/P-002/eventos` | HTTP 200 -> respuesta_vacia_valida / eventos: 0 |
| 2026-10-17T00:33:18Z | api | api | CU06 partido inexistente | OK | 9.7 | `GET http://127.0.0.1:8000/partidos/P-999/eventos` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |
| 2026-10-17T00:33:18Z | api | api | CU08 muro de comentarios | OK | 16.0 | `GET http://127.0.0.1:8000/partidos/P-001/comentarios?ventana=203006152015&limit=5` | HTTP 200 -> exito / items: 5 |
| 2026-10-17T00:33:18Z | api | api | CU08 ventana sin comentarios | OK | 14.2 | `GET http://127.0.0.1:8000/partidos/P-001/comentarios?ventana=203001010000` | HTTP 200 -> respuesta_vacia_valida / items: 0 |
| 2026-10-17T00:33:18Z | api | api | CU10 sesión | OK | 30.2 | `GET http://127.0.0.1:8000/sesiones/S-0001` | HTTP 404 -> recurso_inexistente / SESION_NO_VIGENTE [las sesiones de muestra expiran a los 30 min: 404 SESION_NO_VIGENTE también es válido] |
| 2026-10-17T00:33:18Z | api | api | CU12 estadísticas | OK | 53.7 | `GET http://127.0.0.1:8000/partidos/P-001/estadisticas?desde=2030-06-10T20%3A00%3A00Z&hasta=2030-06-10T20%3A15%3A00Z&resolucion=5m` | HTTP 200 -> exito / series: 2 |
| 2026-10-17T00:33:18Z | api | api | CU12 ventana sin puntos | OK | 12.1 | `GET http://127.0.0.1:8000/partidos/P-001/estadisticas?desde=2031-01-01T00%3A00%3A00Z&hasta=2031-01-01T01%3A00%3A00Z` | HTTP 200 -> respuesta_vacia_valida / series: 0 |
| 2026-10-17T00:33:18Z | api | api | CU12 intervalo invertido | OK | 23.5 | `GET http://127.0.0.1:8000/partidos/P-001/estadisticas?desde=2030-06-10T22%3A00%3A00Z&hasta=2030-06-10T20%3A00%3A00Z` | HTTP 400 -> error_validacion / VALIDACION |
| 2026-10-17T00:33:18Z | api | api | CU13 acta oficial | OK | 19.0 | `GET http://127.0.0.1:8000/partidos-oficiales/P-001` | HTTP 200 -> exito / eventos: 1 |
| 2026-10-17T00:33:18Z | api | api | CU13 acta inexistente | OK | 28.8 | `GET http://127.0.0.1:8000/partidos-oficiales/P-999` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |

## Rutas de la API y log asociado

- `h11-263d20-01` `GET /health/live` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-01 metodo=GET ruta=/health/live estado=200 duracion_ms=1.3`
- `h11-263d20-02` `GET /health/ready` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-02 metodo=GET ruta=/health/ready estado=200 duracion_ms=1.3`
- `h11-263d20-03` `GET /health/dependencias?refrescar=true` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=mongodb operacion=ping resultado=ok duracion_ms=4.2`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=redis operacion=ping resultado=ok duracion_ms=2.1`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=iris operacion=ping resultado=ok duracion_ms=1.4`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=neo4j operacion=ping resultado=ok duracion_ms=6.8`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=influxdb operacion=ping resultado=ok duracion_ms=6.8`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-03 dependencia=cassandra operacion=ping resultado=ok duracion_ms=13.3`
  - `2026-10-17T00:33:18Z INFO [fixture2030.servicio.salud] request_id=h11-263d20-03 diagnostico estado=up mongodb=up neo4j=up cassandra=up redis=up influxdb=up iris=up`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-03 metodo=GET ruta=/health/dependencias estado=200 duracion_ms=18.5`
- `h11-263d20-04` `GET /equipos/ARG` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-04 dependencia=mongodb operacion=equipos.find_one resultado=ok duracion_ms=2.0`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-04 metodo=GET ruta=/equipos/ARG estado=200 duracion_ms=3.3`
- `h11-263d20-05` `GET /equipos/XYZ` -> HTTP 404 (recurso_inexistente)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-05 dependencia=mongodb operacion=equipos.find_one resultado=ok duracion_ms=2.5`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-05 metodo=GET ruta=/equipos/XYZ estado=404 duracion_ms=4.0`
- `h11-263d20-06` `GET /equipos/arg` -> HTTP 400 (error_validacion)
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-06 metodo=GET ruta=/equipos/arg estado=400 duracion_ms=1.0`
- `h11-263d20-07` `GET /equipos/ARG/jugadores?size=5` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-07 dependencia=mongodb operacion=equipos.exists resultado=ok duracion_ms=1.9`
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-07 dependencia=mongodb operacion=jugadores.find_paginado resultado=ok duracion_ms=3.5`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-07 metodo=GET ruta=/equipos/ARG/jugadores estado=200 duracion_ms=7.1`
- `h11-263d20-08` `GET /partidos/P-001` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-08 dependencia=redis operacion=cache_partido.get resultado=ok duracion_ms=1.8`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-08 metodo=GET ruta=/partidos/P-001 estado=200 duracion_ms=4.0`
- `h11-263d20-09` `GET /partidos/P-001/eventos?limit=5` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-09 dependencia=neo4j operacion=partido.eventos resultado=ok duracion_ms=7.5`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-09 metodo=GET ruta=/partidos/P-001/eventos estado=200 duracion_ms=9.2`
- `h11-263d20-10` `GET /partidos/P-002/eventos` -> HTTP 200 (respuesta_vacia_valida)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-10 dependencia=neo4j operacion=partido.eventos resultado=ok duracion_ms=7.2`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-10 metodo=GET ruta=/partidos/P-002/eventos estado=200 duracion_ms=9.1`
- `h11-263d20-11` `GET /partidos/P-999/eventos` -> HTTP 404 (recurso_inexistente)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-11 dependencia=neo4j operacion=partido.eventos resultado=ok duracion_ms=6.7`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-11 metodo=GET ruta=/partidos/P-999/eventos estado=404 duracion_ms=8.1`
- `h11-263d20-12` `GET /partidos/P-001/comentarios?ventana=203006152015&limit=5` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-12 dependencia=cassandra operacion=comentarios_por_partido.select_ventana resultado=ok duracion_ms=12.6`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-12 metodo=GET ruta=/partidos/P-001/comentarios estado=200 duracion_ms=14.4`
- `h11-263d20-13` `GET /partidos/P-001/comentarios?ventana=203001010000` -> HTTP 200 (respuesta_vacia_valida)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-13 dependencia=cassandra operacion=comentarios_por_partido.select_ventana resultado=ok duracion_ms=10.8`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-13 metodo=GET ruta=/partidos/P-001/comentarios estado=200 duracion_ms=12.5`
- `h11-263d20-14` `GET /sesiones/S-0001` -> HTTP 404 (recurso_inexistente)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-14 dependencia=redis operacion=sesion.hmget_ttl resultado=ok duracion_ms=1.8`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-14 metodo=GET ruta=/sesiones/S-0001 estado=404 duracion_ms=3.5`
- `h11-263d20-15` `GET /partidos/P-001/estadisticas?desde=2030-06-10T20%3A00%3A00Z&hasta=2030-06-10T20%3A15%3A00Z&resolucion=5m` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-15 dependencia=influxdb operacion=estadisticas_partido.date_bin resultado=ok duracion_ms=25.0`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-15 metodo=GET ruta=/partidos/P-001/estadisticas estado=200 duracion_ms=27.3`
- `h11-263d20-16` `GET /partidos/P-001/estadisticas?desde=2031-01-01T00%3A00%3A00Z&hasta=2031-01-01T01%3A00%3A00Z` -> HTTP 200 (respuesta_vacia_valida)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-16 dependencia=influxdb operacion=estadisticas_partido.date_bin resultado=ok duracion_ms=8.0`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-16 metodo=GET ruta=/partidos/P-001/estadisticas estado=200 duracion_ms=10.1`
- `h11-263d20-17` `GET /partidos/P-001/estadisticas?desde=2030-06-10T22%3A00%3A00Z&hasta=2030-06-10T20%3A00%3A00Z` -> HTTP 400 (error_validacion)
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-17 metodo=GET ruta=/partidos/P-001/estadisticas estado=400 duracion_ms=1.6`
- `h11-263d20-18` `GET /partidos-oficiales/P-001` -> HTTP 200 (exito)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-18 dependencia=iris operacion=Fixture.API.ObtenerActa resultado=ok duracion_ms=3.2`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-18 metodo=GET ruta=/partidos-oficiales/P-001 estado=200 duracion_ms=5.4`
- `h11-263d20-19` `GET /partidos-oficiales/P-999` -> HTTP 404 (recurso_inexistente)
  - `2026-10-17T00:33:18Z INFO [fixture2030.adaptador] request_id=h11-263d20-19 dependencia=iris operacion=Fixture.API.ObtenerActa resultado=ok duracion_ms=2.2`
  - `2026-10-17T00:33:18Z INFO [fixture2030.acceso] request_id=h11-263d20-19 metodo=GET ruta=/partidos-oficiales/P-999 estado=404 duracion_ms=4.0`

# Matriz de conectividad — Correcciones docentes H4-H10; cinco motores configurados, falta token InfluxDB

| Campo | Valor |
|---|---|
| etiqueta | Correcciones docentes H4-H10; cinco motores configurados, falta token InfluxDB |
| inicio_utc | 2026-10-20T00:10:25Z |
| commit | c55b302 (hito-11, con cambios sin commitear) |
| origen | notebook Windows 11 (PowerShell/cmd); 127.0.0.1 = puertos publicados por Docker |
| python | 3.12.15 |
| drivers | pymongo 4.19.0, neo4j 6.4.1, cassandra-driver 3.30.1, redis 8.1.0, intersystems-irispython 5.4.1 |
| configuracion | fixture2030-hito-10-api-integrada/.env |
| modo | completo |
| productos | mongodb, neo4j, cassandra, redis, influxdb, iris |
| capas | autenticacion, autorizacion, configuracion, contenedor, contexto, lectura, portal_http, protocolo, resolucion, sonda, tcp, api |
| timeouts_s | tcp=3 conexion=2 operacion=5 api=15 |
| fin_utc | 2026-10-20T00:10:35Z |
| duracion_s | 9.6 |

## Matriz por producto

| Producto | Estado | Cfg | DNS | TCP | Prot | AuthN | AuthZ | Ctx | Lect | Sondas | API | Lectura (ms) | Diagnóstico |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mongodb | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 7.8 | todas las capas ejecutadas terminaron OK |
| neo4j | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 4/4 | OK | 6.5 | todas las capas ejecutadas terminaron OK |
| cassandra | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 74.6 | todas las capas ejecutadas terminaron OK |
| redis | **disponible** | OK | OK | OK | OK | OK | OK | OK | WARN | 2/2 | OK | 1.0 | observación: EXISTS/TYPE/PTTL: 'sesion:S-0001' ausente o expirada: EXISTS 0, PTTL -2 |
| influxdb | **no configurado** | WARN | SKIP | SKIP | SKIP | SKIP | SKIP | SKIP | SKIP | - | FAIL | - | no hay token: sin token (no existe fixture2030-influxDB/.influxdb3-token) -> producto no configurado |
| iris | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 80.6 | todas las capas ejecutadas terminaron OK |

## Resultados

| Instante (UTC) | Producto | Capa | Prueba | Estado | ms | Destino | Detalle |
|---|---|---|---|---|---|---|---|
| 2026-10-20T00:10:26Z | mongodb | configuracion | variables | OK | 0.0 | `(configuración)` | MONGO_HOST=127.0.0.1; MONGO_PORT=27017; MONGO_USER=admin; MONGO_PASSWORD (definida, oculta); MONGO_AUTH_DB=admin; MONGO_DATABASE=fixture2030 [origen: archivo fixture2030-hito-10-api-integrada/.env] |
| 2026-10-20T00:10:26Z | mongodb | contenedor | docker inspect | OK | 442.4 | `fixture2030-mongodb` | fixture2030-mongodb: running; puertos publicados: 27017/tcp -> 0.0.0.0:27017. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:26Z | mongodb | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:27017` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-20T00:10:26Z | mongodb | tcp | connect() | OK | 1.4 | `127.0.0.1:27017` | 127.0.0.1:27017 listener aceptó la conexión |
| 2026-10-20T00:10:26Z | mongodb | protocolo | hello (sin credenciales) | OK | 8.2 | `127.0.0.1:27017 database=fixture2030` | primario=True, wire=21, MongoDB 7.0.40 |
| 2026-10-20T00:10:26Z | mongodb | autenticacion | connectionStatus | OK | 27.2 | `127.0.0.1:27017 database=fixture2030` | autenticado como admin@admin (roles: root) |
| 2026-10-20T00:10:26Z | mongodb | autorizacion | listCollections fixture2030 | OK | 1.4 | `127.0.0.1:27017 database=fixture2030` | permitido en 'fixture2030' (2 colecciones) |
| 2026-10-20T00:10:26Z | mongodb | contexto | colecciones esperadas | OK | 0.0 | `127.0.0.1:27017 database=fixture2030` | database 'fixture2030' con las colecciones del módulo: equipos, jugadores |
| 2026-10-20T00:10:26Z | mongodb | lectura | find_one + count_documents | OK | 7.8 | `127.0.0.1:27017 database=fixture2030` | equipos.find_one(_id='ARG') -> Argentina (grupo A); jugadores.count_documents(codigo_equipo='ARG', limit=100) = 23 |
| 2026-10-20T00:10:26Z | mongodb | sonda | documento inexistente | OK | 2.2 | `127.0.0.1:27017 database=fixture2030` | equipos.find_one(_id='ZZZ') -> None: ausencia válida |
| 2026-10-20T00:10:26Z | mongodb | sonda | colección inexistente | OK | 3.2 | `127.0.0.1:27017 database=fixture2030` | fixture2030.coleccion_inexistente_h11.find_one() -> None: colección inexistente, sin error del servidor |
| 2026-10-20T00:10:26Z | mongodb | sonda | database inexistente | OK | 2.7 | `127.0.0.1:27017 database=fixture2030` | fixture2030_inexistente_h11.listCollections -> [] sin error: por eso el contexto verifica colecciones |
| 2026-10-20T00:10:26Z | neo4j | configuracion | variables | OK | 0.2 | `(configuración)` | NEO4J_URI=bolt://127.0.0.1:7687; NEO4J_HTTP_URL=http://127.0.0.1:7474; NEO4J_USER=neo4j; NEO4J_PASSWORD (definida, oculta); NEO4J_DATABASE=neo4j [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-20T00:10:27Z | neo4j | contenedor | docker inspect | OK | 491.6 | `fixture2030-neo4j` | fixture2030-neo4j: running; puertos publicados: 7474/tcp -> 0.0.0.0:7474, 7687/tcp -> 0.0.0.0:7687. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:27Z | neo4j | portal_http | GET Browser/discovery | OK | 48.8 | `http://127.0.0.1:7474` | HTTP 200: Neo4j 2026.07.1 community; anuncia bolt_direct=bolt://127.0.0.1:7687. La API no usa este puerto: no prueba Bolt |
| 2026-10-20T00:10:27Z | neo4j | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:7687` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-20T00:10:27Z | neo4j | tcp | connect() | OK | 0.7 | `127.0.0.1:7687` | 127.0.0.1:7687 listener aceptó la conexión |
| 2026-10-20T00:10:27Z | neo4j | protocolo | get_server_info (driver) | OK | 29.8 | `bolt://127.0.0.1:7687 database=neo4j` | driver Bolt: Neo4j/2026.07.1, protocolo (6, 1); la conexión incluye identidad |
| 2026-10-20T00:10:27Z | neo4j | autenticacion | verify_authentication | OK | 2.6 | `bolt://127.0.0.1:7687 database=neo4j` | usuario 'neo4j' autenticado por Bolt |
| 2026-10-20T00:10:27Z | neo4j | autorizacion | SHOW CURRENT USER | OK | 5.3 | `bolt://127.0.0.1:7687 database=neo4j` | identidad 'neo4j' reconocida; roles=null (Community: sin RBAC, toda identidad autenticada puede leer) |
| 2026-10-20T00:10:27Z | neo4j | contexto | db.info() en 'neo4j' | OK | 10.3 | `bolt://127.0.0.1:7687 database=neo4j` | database 'neo4j' seleccionada; etiquetas: Equipo, Jugador, Sede, Partido, Evento |
| 2026-10-20T00:10:27Z | neo4j | lectura | MATCH parametrizado | OK | 6.5 | `bolt://127.0.0.1:7687 database=neo4j` | Partido P-001 (2030-06-10): equipos ARG, ESP [Cypher parametrizado, LIMIT 1, timeout de operación] |
| 2026-10-20T00:10:27Z | neo4j | sonda | partido inexistente | OK | 4.4 | `bolt://127.0.0.1:7687 database=neo4j` | partido P-999 -> sin filas: partido inexistente (la API responde 404) |
| 2026-10-20T00:10:27Z | neo4j | sonda | resultado vacío | OK | 4.1 | `bolt://127.0.0.1:7687 database=neo4j` | partido P-002 existe con 0 eventos: resultado vacío válido (la API responde 200 con lista vacía) |
| 2026-10-20T00:10:27Z | neo4j | sonda | database inexistente | OK | 4.5 | `bolt://127.0.0.1:7687 database=neo4j` | database 'noexiste_h11' -> Neo.ClientError.Database.DatabaseNotFound: error de contexto, no de conexión (la API lo traduce a 503) |
| 2026-10-20T00:10:28Z | neo4j | sonda | error de conexión | OK | 1014.5 | `bolt://127.0.0.1:7687 database=neo4j` | bolt://127.0.0.1:50460 sin listener -> ServiceUnavailable: error de conexión, distinto de 'sin filas' |
| 2026-10-20T00:10:28Z | cassandra | configuracion | variables | OK | 0.0 | `(configuración)` | CASSANDRA_HOSTS=127.0.0.1; CASSANDRA_PORT=9042; CASSANDRA_KEYSPACE=fixture2030; CASSANDRA_DC=datacenter1; CASSANDRA_TABLA=comentarios_por_partido [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-20T00:10:29Z | cassandra | contenedor | docker inspect | OK | 464.7 | `fixture2030-cassandra` | fixture2030-cassandra: running (healthy); puertos publicados: 9042/tcp -> 0.0.0.0:9042. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:29Z | cassandra | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:9042` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-20T00:10:29Z | cassandra | tcp | connect() | OK | 0.7 | `127.0.0.1:9042` | 127.0.0.1:9042 listener aceptó la conexión |
| 2026-10-20T00:10:30Z | cassandra | protocolo | sesión CQL (driver) | OK | 1351.2 | `127.0.0.1:9042 keyspace=fixture2030` | sesión CQL negociada por cassandra-driver; incluye el intercambio de identidad |
| 2026-10-20T00:10:30Z | cassandra | autenticacion | identidad de la sesión | OK | 0.0 | `127.0.0.1:9042 keyspace=fixture2030` | sesión aceptada sin credenciales, igual que la API del laboratorio; no prueba permisos sobre las tablas |
| 2026-10-20T00:10:30Z | cassandra | autorizacion | SELECT system.local | OK | 15.9 | `127.0.0.1:9042 keyspace=fixture2030` | SELECT system.local permitido: Cassandra 5.0.9, cluster 'Fixture2030_Cassandra', DC 'datacenter1' |
| 2026-10-20T00:10:30Z | cassandra | contexto | metadata keyspace/tabla | OK | 0.0 | `127.0.0.1:9042 keyspace=fixture2030` | keyspace 'fixture2030' ({'class': 'SimpleStrategy', 'replication_factor': '1'}); comentarios_por_partido: partición (id_partido, ventana, shard), clustering (id_comentario); DC configurado 'datacenter1' |
| 2026-10-20T00:10:31Z | cassandra | lectura | SELECT por partición | OK | 74.6 | `127.0.0.1:9042 keyspace=fixture2030` | partición completa (P-001, 203006152015, shard 0..3), LIMIT 5 c/u: 5 filas [2, 3, 0, 0] |
| 2026-10-20T00:10:31Z | cassandra | sonda | tabla inexistente | OK | 16.1 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="table tabla_inexistente_h11 does not exist" -> tabla inexistente; el servidor respondió |
| 2026-10-20T00:10:31Z | cassandra | sonda | keyspace inexistente | OK | 14.5 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="keyspace keyspace_inexistente_h11 does not exist" -> keyspace inexistente; el servidor respondió |
| 2026-10-20T00:10:31Z | cassandra | sonda | partición incompleta | OK | 15.9 | `127.0.0.1:9042 keyspace=fixture2030` | InvalidRequest: Error from server: code=2200 [Invalid query] message="Cannot execute this query as it might involve data filtering and t -> la consulta no respeta el patrón de partición y exigiría ALLOW FILTERING |
| 2026-10-20T00:10:31Z | redis | configuracion | variables | OK | 0.0 | `(configuración)` | REDIS_HOST=127.0.0.1; REDIS_PORT=6379; REDIS_PASSWORD (vacía); REDIS_DB=0; REDIS_CLAVE_PRUEBA=sesion:S-0001 [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-20T00:10:31Z | redis | contenedor | docker inspect | OK | 430.9 | `fixture2030-redis` | fixture2030-redis: running; puertos publicados: 6379/tcp -> 0.0.0.0:6379. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:31Z | redis | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:6379` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-20T00:10:31Z | redis | tcp | connect() | OK | 12.6 | `127.0.0.1:6379` | 127.0.0.1:6379 listener aceptó la conexión |
| 2026-10-20T00:10:31Z | redis | protocolo | PING (redis-py) | OK | 27.8 | `127.0.0.1:6379 db=0` | PING mediante redis-py -> PONG (sin credenciales) |
| 2026-10-20T00:10:31Z | redis | autenticacion | ACL WHOAMI | OK | 6.0 | `127.0.0.1:6379 db=0` | sin contraseña configurada; el servidor acepta la conexión como 'default' (laboratorio) |
| 2026-10-20T00:10:31Z | redis | autorizacion | DBSIZE | OK | 1.0 | `127.0.0.1:6379 db=0` | permitido: 0 claves en la base lógica |
| 2026-10-20T00:10:31Z | redis | contexto | CLIENT INFO + INFO keyspace | OK | 3.1 | `127.0.0.1:6379 db=0` | Redis 8.10.2; base lógica db=0: 0 claves, 0 con TTL |
| 2026-10-20T00:10:31Z | redis | lectura | EXISTS/TYPE/PTTL | WARN | 1.0 | `127.0.0.1:6379 db=0` | 'sesion:S-0001' ausente o expirada: EXISTS 0, PTTL -2 |
| 2026-10-20T00:10:31Z | redis | sonda | clave ausente | OK | 1.3 | `127.0.0.1:6379 db=0` | EXISTS diag:h11:inexistente:32ecef8c = 0, PTTL = -2: ausencia válida (nil), no es error |
| 2026-10-20T00:10:31Z | redis | sonda | clave expirada | SKIP | 0.0 | `127.0.0.1:6379 db=0` | desactivada (REDIS_SONDA_EXPIRACION=0): escribe una clave diag: de 1,5 s |
| 2026-10-20T00:10:33Z | redis | sonda | Redis no disponible | OK | 2008.2 | `127.0.0.1:6379 db=0` | 127.0.0.1:50471 sin servidor -> TimeoutError en 2004 ms: excepción, distinta de nil (la API responde 503/504, nunca 404). En Windows el rechazo en 127.0.0.1 tarda ~2 s (reintentos de SYN): con TIMEOUT_CONEXION_S=2 la caída se informa como timeout (504). |
| 2026-10-20T00:10:33Z | influxdb | configuracion | variables | OK | 0.0 | `(configuración)` | INFLUX_URL=http://127.0.0.1:8181; INFLUX_DATABASE=fixture2030; INFLUX_TOKEN (vacía); INFLUX_TOKEN_FILE=../fixture2030-influxDB/.influxdb3-token [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-20T00:10:33Z | influxdb | configuracion | origen del token | WARN | - | `http://127.0.0.1:8181 database=fixture2030` | no hay token: sin token (no existe fixture2030-influxDB/.influxdb3-token) -> producto no configurado |
| 2026-10-20T00:10:34Z | influxdb | contenedor | docker inspect | OK | 432.4 | `fixture2030-influxdb` | fixture2030-influxdb: running; puertos publicados: 8181/tcp -> 127.0.0.1:8181. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:34Z | influxdb | resolucion | getaddrinfo | SKIP | - | `127.0.0.1:8181` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | tcp | connect() | SKIP | - | `127.0.0.1:8181` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | protocolo | GET /health (sin token) | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | autenticacion | GET /health (con token) | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | autorizacion | listar databases | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | contexto | database + tabla | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | lectura | COUNT acotado por tiempo | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | influxdb | lectura | agregación date_bin | SKIP | - | `http://127.0.0.1:8181 database=fixture2030` | no evaluada: no ejecutada: falta el token de InfluxDB |
| 2026-10-20T00:10:34Z | iris | configuracion | variables | OK | 0.0 | `(configuración)` | IRIS_HOST=127.0.0.1; IRIS_PORT=1972; IRIS_PORTAL_URL=http://127.0.0.1:52773/csp/sys/UtilHome.csp; IRIS_NAMESPACE=USER; IRIS_USER=fixture_api_read; IRIS_PASSWORD (definida, oculta) [origen: archivo fixture2030-hito-10-api-integrada/.env, defecto] |
| 2026-10-20T00:10:34Z | iris | contenedor | docker inspect | OK | 428.4 | `fixture2030-iris` | fixture2030-iris: running (healthy); puertos publicados: 1972/tcp -> 0.0.0.0:1972, 52773/tcp -> 0.0.0.0:52773. Activo no implica disponible: lo deciden las capas siguientes |
| 2026-10-20T00:10:34Z | iris | portal_http | GET Management Portal | OK | 65.2 | `http://127.0.0.1:52773/csp/sys/UtilHome.csp` | HTTP 200: el Management Portal responde. La API no usa este puerto: no prueba el Superserver |
| 2026-10-20T00:10:34Z | iris | resolucion | getaddrinfo | OK | 0.0 | `127.0.0.1:1972` | '127.0.0.1' es una dirección IP literal: no requiere DNS |
| 2026-10-20T00:10:34Z | iris | tcp | connect() | OK | 15.8 | `127.0.0.1:1972` | 127.0.0.1:1972 listener aceptó la conexión |
| 2026-10-20T00:10:34Z | iris | protocolo | handshake Superserver | OK | 44.2 | `127.0.0.1:1972 namespace=USER` | el Superserver completó el handshake |
| 2026-10-20T00:10:34Z | iris | autenticacion | login en USER | OK | 44.2 | `127.0.0.1:1972 namespace=USER` | usuario 'fixture_api_read' aceptado en el namespace 'USER' |
| 2026-10-20T00:10:34Z | iris | autorizacion | %SYSTEM.Version.GetNumber | OK | 1.8 | `127.0.0.1:1972 namespace=USER` | Native API puede ejecutar métodos de clase: IRIS 2026.2 |
| 2026-10-20T00:10:34Z | iris | contexto | namespace + clase | OK | 3.3 | `127.0.0.1:1972 namespace=USER` | namespace activo 'USER'; clase Fixture.Partido compilada |
| 2026-10-20T00:10:34Z | iris | lectura | SELECT del acta (DB-API) | OK | 80.6 | `127.0.0.1:1972 namespace=USER` | SELECT parametrizado: acta 'P-009', estado 'Finalizado', sede 'Estadio Centenario' |
| 2026-10-20T00:10:34Z | iris | sonda | objeto inexistente | OK | 1.0 | `127.0.0.1:1972 namespace=USER` | SELECT de 'P-999' sin filas: ausencia de negocio (HTTP 404), no falla de conexión |
| 2026-10-20T00:10:34Z | iris | sonda | clase inexistente | OK | 1.6 | `127.0.0.1:1972 namespace=USER` | <CLASS DOES NOT EXIST>XDCall+11^%SYS.DBSRV.1: error de metadato, no de conexión |
| 2026-10-20T00:10:34Z | iris | sonda | namespace incorrecto | OK | 0.9 | `127.0.0.1:1972 namespace=USER` | %SYS.Namespace.Exists('NOEXISTE_H11') = 0: con un namespace inexistente iris.connect devuelve 'Access Denied', igual que una credencial inválida; esta consulta los distingue sin provocar logins fallidos |
| 2026-10-20T00:10:34Z | api | api | liveness | OK | 2.7 | `GET http://127.0.0.1:50435/health/live` | HTTP 200 -> exito / estado=up [no consulta bases] |
| 2026-10-20T00:10:34Z | api | api | readiness | WARN | 3.0 | `GET http://127.0.0.1:50435/health/ready` | HTTP 200 -> exito / listo=True estado=degraded no_disponibles=['influxdb'] [diagnóstico reutilizado (TTL)] |
| 2026-10-20T00:10:34Z | api | api | diagnóstico por dependencia | WARN | 21.8 | `GET http://127.0.0.1:50435/health/dependencias?refrescar=true` | HTTP 200 -> exito / estado=degraded mongodb=up neo4j=up cassandra=up redis=up influxdb=not_configured iris=up |
| 2026-10-20T00:10:34Z | api | api | CU01 equipo | OK | 24.8 | `GET http://127.0.0.1:50435/equipos/ARG` | HTTP 200 -> exito / nombre=Argentina |
| 2026-10-20T00:10:34Z | api | api | CU01 equipo inexistente | OK | 15.0 | `GET http://127.0.0.1:50435/equipos/XYZ` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |
| 2026-10-20T00:10:34Z | api | api | CU01 código inválido | OK | 1.9 | `GET http://127.0.0.1:50435/equipos/arg` | HTTP 400 -> error_validacion / VALIDACION [no llega a la base] |
| 2026-10-20T00:10:34Z | api | api | CU06 eventos | OK | 7.7 | `GET http://127.0.0.1:50435/partidos/P-001/eventos?limit=5` | HTTP 200 -> exito / eventos: 1 |
| 2026-10-20T00:10:34Z | api | api | CU06 partido sin eventos | OK | 24.3 | `GET http://127.0.0.1:50435/partidos/P-002/eventos` | HTTP 200 -> respuesta_vacia_valida / eventos: 0 |
| 2026-10-20T00:10:34Z | api | api | CU06 partido inexistente | OK | 32.7 | `GET http://127.0.0.1:50435/partidos/P-999/eventos` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |
| 2026-10-20T00:10:34Z | api | api | CU08 muro de comentarios | OK | 10.3 | `GET http://127.0.0.1:50435/partidos/P-001/comentarios?ventana=203006152015&limit=5` | HTTP 200 -> exito / items: 5 |
| 2026-10-20T00:10:35Z | api | api | CU08 ventana sin comentarios | OK | 15.9 | `GET http://127.0.0.1:50435/partidos/P-001/comentarios?ventana=203001010000` | HTTP 200 -> respuesta_vacia_valida / items: 0 |
| 2026-10-20T00:10:35Z | api | api | CU10 sesión | OK | 4.2 | `GET http://127.0.0.1:50435/sesiones/S-0001` | HTTP 404 -> recurso_inexistente / SESION_NO_VIGENTE [las sesiones de muestra expiran a los 30 min: 404 SESION_NO_VIGENTE también es válido] |
| 2026-10-20T00:10:35Z | api | api | CU12 estadísticas | FAIL | 3.0 | `GET http://127.0.0.1:50435/partidos/P-001/estadisticas?desde=2030-06-10T20%3A00%3A00Z&hasta=2030-06-10T20%3A15%3A00Z&resolucion=5m` | HTTP 503 -> dependencia_no_disponible / DEPENDENCIA_NO_DISPONIBLE (dependencia=influxdb) — hipótesis: API alcanzable, dependencia fallida: DEPENDENCIA_NO_DISPONIBLE (dependencia=influxdb). La API identifica la fuente en lugar de responder 200 vacío. — siguiente paso: Contrastar con las pruebas nativas del mismo producto: si el cliente nativo funciona, revisar la configuración de la API. |
| 2026-10-20T00:10:35Z | api | api | CU12 ventana sin puntos | FAIL | 2.4 | `GET http://127.0.0.1:50435/partidos/P-001/estadisticas?desde=2031-01-01T00%3A00%3A00Z&hasta=2031-01-01T01%3A00%3A00Z` | HTTP 503 -> dependencia_no_disponible / DEPENDENCIA_NO_DISPONIBLE (dependencia=influxdb) — hipótesis: API alcanzable, dependencia fallida: DEPENDENCIA_NO_DISPONIBLE (dependencia=influxdb). La API identifica la fuente en lugar de responder 200 vacío. — siguiente paso: Contrastar con las pruebas nativas del mismo producto: si el cliente nativo funciona, revisar la configuración de la API. |
| 2026-10-20T00:10:35Z | api | api | CU12 intervalo invertido | OK | 2.8 | `GET http://127.0.0.1:50435/partidos/P-001/estadisticas?desde=2030-06-10T22%3A00%3A00Z&hasta=2030-06-10T20%3A00%3A00Z` | HTTP 400 -> error_validacion / VALIDACION |
| 2026-10-20T00:10:35Z | api | api | CU13 acta oficial | OK | 4.4 | `GET http://127.0.0.1:50435/partidos-oficiales/P-009` | HTTP 200 -> exito / eventos: 2 |
| 2026-10-20T00:10:35Z | api | api | CU13 acta inexistente | OK | 3.4 | `GET http://127.0.0.1:50435/partidos-oficiales/P-999` | HTTP 404 -> recurso_inexistente / RECURSO_NO_ENCONTRADO |

## Rutas de la API y log asociado

- `h11-025d2e-01` `GET /health/live` -> HTTP 200 (exito)
- `h11-025d2e-02` `GET /health/ready` -> HTTP 200 (exito)
- `h11-025d2e-03` `GET /health/dependencias?refrescar=true` -> HTTP 200 (exito)
- `h11-025d2e-04` `GET /equipos/ARG` -> HTTP 200 (exito)
- `h11-025d2e-05` `GET /equipos/XYZ` -> HTTP 404 (recurso_inexistente)
- `h11-025d2e-06` `GET /equipos/arg` -> HTTP 400 (error_validacion)
- `h11-025d2e-07` `GET /partidos/P-001/eventos?limit=5` -> HTTP 200 (exito)
- `h11-025d2e-08` `GET /partidos/P-002/eventos` -> HTTP 200 (respuesta_vacia_valida)
- `h11-025d2e-09` `GET /partidos/P-999/eventos` -> HTTP 404 (recurso_inexistente)
- `h11-025d2e-10` `GET /partidos/P-001/comentarios?ventana=203006152015&limit=5` -> HTTP 200 (exito)
- `h11-025d2e-11` `GET /partidos/P-001/comentarios?ventana=203001010000` -> HTTP 200 (respuesta_vacia_valida)
- `h11-025d2e-12` `GET /sesiones/S-0001` -> HTTP 404 (recurso_inexistente)
- `h11-025d2e-13` `GET /partidos/P-001/estadisticas?desde=2030-06-10T20%3A00%3A00Z&hasta=2030-06-10T20%3A15%3A00Z&resolucion=5m` -> HTTP 503 (dependencia_no_disponible)
- `h11-025d2e-14` `GET /partidos/P-001/estadisticas?desde=2031-01-01T00%3A00%3A00Z&hasta=2031-01-01T01%3A00%3A00Z` -> HTTP 503 (dependencia_no_disponible)
- `h11-025d2e-15` `GET /partidos/P-001/estadisticas?desde=2030-06-10T22%3A00%3A00Z&hasta=2030-06-10T20%3A00%3A00Z` -> HTTP 400 (error_validacion)
- `h11-025d2e-16` `GET /partidos-oficiales/P-009` -> HTTP 200 (exito)
- `h11-025d2e-17` `GET /partidos-oficiales/P-999` -> HTTP 404 (recurso_inexistente)

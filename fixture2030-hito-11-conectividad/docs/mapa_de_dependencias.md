# Mapa de dependencias (RF1, sección 5.1)

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Dependencias de la API integrada del Hito 10, vistas **desde el proceso que
inicia la conexión**. Las credenciales se nombran por su variable y su mecanismo;
su valor no se publica.

* **Proceso que conecta:** `uvicorn app.main:app` (Python 3.12) en la notebook, escuchando en `127.0.0.1:8000`. Usa un adaptador por producto (`app/adapters/*_adapter.py`) y los timeouts `TIMEOUT_CONEXION_S=2` y `TIMEOUT_OPERACION_S=5`.
* **Estado observado:** corrida de `scripts/generar_evidencia.sh` del 2026-10-17 00:33 UTC ([`evidencia/resultados_completo.txt`](evidencia/resultados_completo.txt)).
* **Productos no integrados:** ninguno. Los seis productos de la cursada están integrados en el Hito 10. Si una variable imprescindible falta, el diagnóstico y `/health/dependencias` informan el producto como **no configurado** (`not_configured`), nunca como caído.

## 1. Mapa por producto

| | MongoDB | Neo4j | Cassandra | Redis | InfluxDB 3 Core | InterSystems IRIS |
|---|---|---|---|---|---|---|
| **Módulo del Fixture** | Equipos y jugadores (Hito 4) | Partidos, eventos y relaciones (Hito 5) | Comentarios (Hito 6) | Sesiones y caché de partidos (Hito 7); idempotencia de escrituras | Estadísticas temporales (Hito 8) | Actas oficiales (Hito 9) |
| **Adaptador** | `mongo_adapter.py` | `neo4j_adapter.py` | `cassandra_adapter.py` | `redis_adapter.py` | `influx_adapter.py` | `iris_adapter.py` |
| **Host desde la notebook** | `127.0.0.1` | `127.0.0.1` | `127.0.0.1` | `127.0.0.1` | `127.0.0.1` | `127.0.0.1` |
| **Host desde la red Docker** | `mongodb` | `neo4j` | `cassandra` | `redis` | `influxdb` | `iris` |
| **Puerto / protocolo de la API** | 27017 / MongoDB Wire Protocol | 7687 / Bolt 5.8 | 9042 / CQL nativo (v5) | 6379 / RESP | 8181 / HTTP (API v3) | 1972 / Superserver (Native API) |
| **Otros puertos (no usados por la API)** | — | 7474 / HTTP (Browser) | — | — | — | 52773 / HTTP (Management Portal) |
| **Contexto** | database `fixture2030` (`MONGO_DATABASE`); colecciones `equipos`, `jugadores` | database `neo4j` (`NEO4J_DATABASE`) | keyspace `fixture2030` (`CASSANDRA_KEYSPACE`), DC `datacenter1`; tablas `comentarios_por_partido`, `comentarios_por_usuario` | base lógica `db=0` (`REDIS_DB`); claves `sesion:*`, `cache:partido:*`, `idem:*` | database `fixture2030` (`INFLUX_DATABASE`); tabla `estadisticas_partido` | namespace `USER` (`IRIS_NAMESPACE`); clases `Fixture.*` y fachada `Fixture.API` |
| **Autenticación** | usuario `MONGO_USER` + `MONGO_PASSWORD`, SCRAM, `authSource=admin` | `NEO4J_USER` + `NEO4J_PASSWORD` (basic auth sobre Bolt) | ninguna en el laboratorio (`AllowAllAuthenticator`) | ninguna en el laboratorio (usuario ACL `default`) | token Bearer: `INFLUX_TOKEN` o el archivo `fixture2030-influxDB/.influxdb3-token` (excluido del repo) | `IRIS_USER=fixture_api` + `IRIS_PASSWORD`, rol mínimo `FixtureAPI` (`%DB_USER`, `%Native_ClassExecution:U`) |
| **Autorización** | rol `root` (usuario de laboratorio) | Community: sin RBAC (`roles=null`) | `AllowAllAuthorizer` | sin ACL restrictivas | token de administración | `FixtureAPI`: solo la base `USER` y ejecución de métodos de clase |
| **Cliente / driver** | pymongo 4.19.0 | neo4j 6.4.1 | cassandra-driver 3.30.1 (+ pyasyncore) | redis-py 8.1.0 | HTTP (httpx en la API, urllib en el diagnóstico) | intersystems-irispython 5.4.1 |
| **Operación mínima (diagnóstico)** | `hello`; `connectionStatus`; `listCollections`; `equipos.find_one({_id:'ARG'})` + `count_documents(limit=100)` | handshake Bolt; `verify_authentication`; `SHOW CURRENT USER`; `db.info()`; `MATCH (p:Partido {codigo_partido:$codigo}) … LIMIT 1` | frames OPTIONS y STARTUP; `SELECT … FROM system.local`; metadata; `SELECT … WHERE id_partido=? AND ventana=? AND shard=? LIMIT 5` | `PING` (RESP); `ACL WHOAMI`; `DBSIZE`; `CLIENT INFO`; `EXISTS/TYPE/PTTL sesion:S-0001` | `GET /health`; `GET /api/v3/configure/database`; `information_schema.tables`; `COUNT(*)` y `date_bin(5 min)` en 15 minutos | `iris.connect`; `%SYSTEM.Version.GetNumber`; `%SYSTEM.SYS.NameSpace`; `%Dictionary.CompiledClass.%ExistsId`; `Fixture.API.ObtenerActa('P-001')` |
| **Ping de salud de la API** | `list_collection_names` de las colecciones esperadas (verifica el contexto) | `RETURN 1` en la database | `SELECT release_version FROM system.local` | `PING` | `SELECT 1` en la database | `%SYSTEM.Version.GetNumber` |
| **Endpoints de la API** | `/equipos`, `/equipos/{iso}`, `/equipos/{iso}/jugadores`, `/jugadores/{id}` | `/partidos/{codigo}`, `/partidos/{codigo}/eventos`, `/equipos/{iso}/rivales` | `GET`/`POST /partidos/{codigo}/comentarios` | `GET`/`DELETE /sesiones/{id}`; caché de `/partidos/{codigo}`; idempotencia de los `POST` | `/partidos/{codigo}/estadisticas` | `/partidos-oficiales/{codigo}`, `…/estado`, `…/eventos` |
| **Estado esperado** | disponible | disponible | disponible | disponible | disponible | disponible |
| **Estado observado** | **disponible** (lectura 3,5 ms) | **disponible** (5,9 ms) | **disponible** (77,2 ms, 4 particiones) | **disponible**; clave de prueba ausente (TTL vencido) | **disponible** (34,2 ms, 1800 puntos + date_bin) | **disponible** (3,3 ms) |

## 2. Dependencias transversales

| Dependencia | Usada por | Si falla |
|---|---|---|
| Redis (caché `cache:partido:*`) | `GET /partidos/{codigo}` | La ficha se lee de Neo4j y responde 200 con `X-Cache: BYPASS` (degradación aceptada en el Hito 10) |
| Redis (idempotencia `idem:*`) | `POST` de comentarios y eventos de acta | La escritura **no** se realiza y responde 503/504: no se escribe sin garantía de no duplicar |
| Neo4j (existencia del partido) | `POST /partidos/{codigo}/comentarios`, `/equipos/{iso}/rivales` | 503/504 de Neo4j; no se escribe en Cassandra |
| MongoDB (existencia del equipo) | `/equipos/{iso}/jugadores`, `/equipos/{iso}/rivales` | 503/504 de MongoDB |
| Archivo de token de InfluxDB | Adaptador de InfluxDB | Sin token: `not_configured` en `/health/dependencias`; 503 en la ruta |

## 3. Datos de prueba que usa el diagnóstico

Todos son datos de laboratorio del propio equipo, cargados por los hitos
anteriores y por `scripts/preparar_datos.sh` del Hito 10. Se pueden cambiar por
variable de entorno sin tocar el código.

| Variable | Valor | Por qué |
|---|---|---|
| `MONGO_EQUIPO_PRUEBA` | `ARG` | Equipo con plantel completo (23 jugadores) |
| `NEO4J_PARTIDO_PRUEBA` / `NEO4J_PARTIDO_SIN_EVENTOS` | `P-001` / `P-002` | Partido con evento y partido existente sin eventos (resultado vacío válido) |
| `CASSANDRA_PARTIDO_PRUEBA` + `CASSANDRA_VENTANA_PRUEBA` | `P-001` + `203006152015` | Partición con comentarios de la muestra del Hito 6 |
| `REDIS_CLAVE_PRUEBA` | `sesion:S-0001` | Sesión del Hito 7, con TTL de 1800 s: muestra la diferencia entre clave ausente y Redis caído |
| `INFLUX_PARTIDO_PRUEBA`, `INFLUX_DESDE`, `INFLUX_HASTA` | `P-001`, 20:00–20:15 del 2030-06-10 | Ventana acotada de 15 minutos (1800 puntos) |
| `IRIS_ACTA_PRUEBA` | `P-001` | Acta en juego con árbitro y un evento |

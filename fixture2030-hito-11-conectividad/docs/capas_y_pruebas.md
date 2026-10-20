# Capas de evaluación, pruebas nativas y pruebas de la API

> Revisión del 19/10/2026: los archivos de evidencia del 17/10 son históricos.
> La implementación actual usa drivers oficiales, valida las respuestas negativas
> y corrige el resumen y el modo estricto. No se deben atribuir los resultados
> anteriores al código corregido. Ver [walkthrough de las correcciones](walkthrough_correcciones.md)
> y [evidencia nueva](evidencia/revision_2026-10-19/README.md).


Grupo 4 — Ingeniería de Datos II — Fixture 2030

Cubre las secciones 5.2 a 5.5 del enunciado y los requisitos RF4 a RF15,
RNF2 y RNF4. Los valores medidos salen de la corrida del 2026-10-17
([`evidencia/resultados_clientes.txt`](evidencia/resultados_clientes.txt) y
[`evidencia/resultados_api.txt`](evidencia/resultados_api.txt)).

## 1. Secuencia y regla de bloqueo

```
Configuración → Resolución → TCP → Protocolo → Autenticación → Autorización → Contexto → Lectura → API
     (gratis)                                                                         (más costoso)
```

* Cada producto recorre las capas **en este orden**. Si una capa falla, las siguientes se registran como **SKIP "no evaluada: falló la capa X"** y no se ejecutan. El diagnóstico apunta a la primera capa rota y no acumula errores derivados (`Cadena` en `scripts/conectividad/registro.py`).
* Las sondas que necesitan datos requieren contexto válido: si falta el keyspace o la tabla no se ejecutan ni se presentan como OK.
* Las pruebas **secundarias** (estado del contenedor, portal HTTP, sondas negativas) nunca bloquean la cadena: informan.
* Cada producto se evalúa por separado. Que falle uno no impide evaluar a los demás (RNF13).
* Todas las esperas tienen límite (RNF5): `TCP_TIMEOUT_S=3`, `TIMEOUT_CONEXION_S=2`, `TIMEOUT_OPERACION_S=5` y `API_TIMEOUT_S=15`. El cliente de IRIS se ejecuta en un hilo con límite de conexión + operación.

## 2. Qué responde cada capa y qué no permite concluir todavía

| Capa | Pregunta que responde | Lo que **no** permite concluir |
|---|---|---|
| Configuración | ¿Están todas las variables y de dónde salió cada valor? | Que los valores sean correctos |
| Resolución | ¿El nombre se convierte en una dirección **desde este origen**? | Que haya algo escuchando |
| TCP | ¿Hay un listener que acepta conexiones en ese host y puerto? | Que sea el producto correcto ni que hable su protocolo |
| Protocolo | ¿El listener habla el protocolo del producto (Bolt, CQL, RESP, Wire, HTTP, Superserver)? | Que la credencial sirva |
| Autenticación | ¿La identidad configurada es aceptada? | Que pueda usar el contexto del módulo |
| Autorización | ¿Esa identidad puede ejecutar una operación de lectura? | Que el contexto sea el del Fixture |
| Contexto | ¿Existe y es el esperado el database, keyspace, namespace o base lógica, con sus colecciones, tablas o clases? | Que existan los datos de prueba |
| Lectura | ¿La operación mínima del módulo funciona? | Rendimiento o volumen (Hito 12) |
| API | ¿La cadena cliente HTTP → API → adaptador → producto funciona y diferencia los casos? | Comportamiento bajo carga |

## 3. Prueba TCP y tipos de falla

`conectividad/red.py` hace `connect()` con la biblioteca estándar (sin `nc`,
que no está en Git Bash) y clasifica el resultado. Cada fila tiene un caso
**observado**:

| Resultado | Interpretación | Caso observado (evidencia) |
|---|---|---|
| Conexión exitosa | Existe un listener accesible en ese host y puerto | Los seis puertos desde la notebook (0,4–25 ms) — `resultados_tcp.txt` |
| *Connection refused* | El host responde, pero nadie escucha: contenedor detenido, puerto no publicado o puerto equivocado | MongoDB detenido: `127.0.0.1:27017 connection refused tras 2057 ms` (`fallo_controlado_mongodb.txt`). `REDIS_PORT=6380`: rechazo tras 2042 ms (A3). Dentro de Docker: rechazo en 0–10 ms |
| Timeout | No hubo respuesta en el plazo: ruta, firewall o host equivocado | `10.255.255.1:9042` sin respuesta: `NoHostAvailable(OSError)` a los 1009 ms (sonda de Cassandra) |
| Host no resuelto | El nombre no existe en este entorno | `MONGO_HOST=mongodb` desde la notebook: `getaddrinfo failed` (A1) |
| Puerto incorrecto | El TCP funciona, pero el listener es otro: se detecta en la capa de **protocolo** | `NEO4J_URI=bolt://127.0.0.1:7474`: TCP OK y handshake Bolt con respuesta `HTTP/1.1 400 Bad Request` (A2) |

> Un TCP exitoso **no** prueba autenticación, autorización, contexto ni
> consulta. Por eso, en el modo `--modo tcp`, la matriz deja cada producto en
> **desconocido** ("solo se probó hasta la capa tcp").

## 4. Pruebas por producto

### MongoDB (RF9)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Alcanzabilidad de `MONGO_HOST:MONGO_PORT` | `connect()` | `127.0.0.1:27017` aceptó (25,3 ms) |
| Conexión con el driver | `hello` sin credenciales, `buildInfo` | primario=True, wire 21, MongoDB 7.0.43 |
| Autenticación | `connectionStatus` con usuario | `admin@admin`, rol `root` |
| Database utilizada | `listCollections` en `fixture2030` + colecciones esperadas | `equipos` y `jugadores` presentes |
| Lectura limitada (equipos/jugadores) | `equipos.find_one({_id:'ARG'})`, `jugadores.count_documents({codigo_equipo:'ARG'}, limit=100)` | Argentina (grupo A); 23 jugadores (3,0 ms) |
| Documento inexistente | `find_one({_id:'ZZZ'})` | `None`: ausencia válida → la API responde 404 |
| Colección o database inexistente | `find_one` en `coleccion_inexistente_h11`; `listCollections` en `fixture2030_inexistente_h11` | `None` y `[]` **sin error**: MongoDB no distingue. Por eso la capa de contexto (y ahora la API) verifica las colecciones |
| Cliente nativo OK vs. API fallando | Matriz: columnas nativas OK y columna API FAIL → **degradado** | Escenario B1: con `MONGO_DATABASE` errónea en la API, el nativo con la configuración correcta da OK y la API da 503 |

Sin credenciales, `listCollections` falla con código 13 (Unauthorized), y una
contraseña errónea falla con código 18 (AuthenticationFailed, escenario A5). Son
la autorización y la autenticación separadas.

### Neo4j (RF10)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Acceso HTTP al Browser | `GET http://127.0.0.1:7474` (JSON de discovery) | 200: Neo4j 2026.07.1 community. **La API no usa este puerto** |
| Acceso Bolt de la API | `driver.get_server_info()` | Ver corrida corregida del 19/10; el driver negocia Bolt e identidad |
| Autenticación | `driver.verify_authentication()` | Usuario `neo4j` autenticado |
| Autorización | `SHOW CURRENT USER` (database `system`) | `roles=null`: Community no tiene RBAC |
| Database seleccionada | `CALL db.info()` + `db.labels()` en `neo4j` | Etiquetas Equipo, Jugador, Sede, Partido, Evento |
| Lectura Cypher parametrizada y acotada | `MATCH (p:Partido {codigo_partido: $codigo}) … LIMIT 1` con timeout | P-001 (2030-06-10): ARG, ESP (7,1 ms) |
| Partido inexistente vs. resultado vacío vs. error de conexión | `P-999` / `P-002` / Bolt a un puerto sin listener | sin filas (404) / existe con 0 eventos (200 vacío) / `ServiceUnavailable` |

### Cassandra (RF11)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Puerto CQL | `connect()` TCP + `cluster.connect()` del driver | Protocolo negociado por el driver; sin parser binario propio |
| Sesión mediante driver | `cluster.connect()` + `SELECT system.local` con timeout | En el laboratorio no se envían credenciales; se informan sesión e identidad por separado |
| Keyspace seleccionado | Metadata del driver | `fixture2030`, SimpleStrategy RF=1 |
| Tabla y patrón de partición | Metadata de `comentarios_por_partido` | Partición `(id_partido, ventana, shard)`, clustering `(id_comentario)` |
| Lectura limitada | `SELECT … WHERE id_partido=? AND ventana=? AND shard=? LIMIT 5` en los 4 shards | 5 filas [2, 3, 0, 0] (74,9 ms) |
| Keyspace o tabla inexistente | `SELECT` sobre `keyspace_inexistente_h11.t` y `tabla_inexistente_h11` | `InvalidRequest` código 2200: el servidor respondió |
| Timeout de conexión vs. consulta inválida | Contact point sin ruta (`10.255.255.1`) vs. `InvalidRequest` | `NoHostAvailable(OSError)` a los 1009 ms vs. respuesta en 15 ms |
| (extra) Modelo de partición | `SELECT` solo con `id_partido` | `InvalidRequest`: exige `ALLOW FILTERING`; el modelo obliga a usar la partición completa |

Hallazgo: si el **keyspace configurado** no existe, `cluster.connect(keyspace)`
falla con `NoHostAvailable("Unable to connect to any servers using keyspace …")`,
el mismo tipo de error que una red caída. El diagnóstico lo separa: primero
conecta sin keyspace y después consulta la metadata (escenario A4a).

### Redis (RF12)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Conexión al servidor | `connect()` | 6379 aceptó |
| Respuesta de protocolo básico | `PING` mediante redis-py | `PONG`; no se serializa RESP manualmente |
| Autenticación si está configurada | `ACL WHOAMI` | Sin contraseña: usuario `default` (laboratorio) |
| Lectura de una clave de demostración | `EXISTS` / `TYPE` / `PTTL` de `sesion:S-0001` | `EXISTS 0`, `PTTL -2`: **ausente** (WARN con explicación) |
| TTL o expiración | Sonda opcional: `SET diag:h11:expira:<id> PX 1500 NX`, `PTTL`, espera de 1,7 s | `PTTL 1499 ms` → `EXISTS 0`, `PTTL -2` |
| Clave ausente vs. expirada vs. Redis no disponible | Clave aleatoria / sonda de expiración / cliente a un puerto sin servidor | `-2` / `-2` (solo el TTL observado antes las distingue) / **excepción** `TimeoutError` a los 2002 ms (Windows) o `ConnectionError` en 2 ms (Docker) |

### InfluxDB 3 Core (RF13)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Endpoint HTTP de salud | `GET /health` sin token | **401**: el servicio responde y exige token también en `/health` |
| Autorización y token sin exponerlo | `GET /health` con token; `GET /api/v3/configure/database` | 200 OK; databases `_internal`, `fixture2030`. El token se lee del archivo y nunca se imprime |
| Database configurada | Listado + `information_schema.tables` | `fixture2030` con `estadisticas_partido` |
| Consulta temporal acotada | `COUNT(*), MIN(time), MAX(time)` con `partido_id=$partido` y `[20:00, 20:15)` | 1800 puntos (20,5 ms) |
| Rango y agregación | `date_bin(INTERVAL '5 minutes', time)` + `AVG(posesion_pct)` | 3 bloques |
| Servicio accesible vs. database inexistente vs. token inválido vs. sin puntos | Sondas | 401 con un token inválido / 404 `database not found` / 200 con `COUNT = 0` en 2031 |

### InterSystems IRIS (RF14)

| Exigido | Prueba | Resultado observado |
|---|---|---|
| Portal HTTP | `GET /csp/sys/UtilHome.csp` | 200. **La API no usa este puerto** |
| Superserver | `connect()` a 1972 + `iris.connect` (Native API) | Handshake completado |
| Usuario y namespace | `iris.connect(..., "USER", "fixture_api", …)`; `%SYSTEM.SYS.NameSpace` | Login aceptado; namespace activo `USER` |
| Cliente utilizado | Native API de Python 5.4.1 (el mismo de la API) y, aparte, la terminal `iris session` | Ver §5 |
| Lectura de entidad o metadato | `%Dictionary.CompiledClass.%ExistsId('Fixture.Partido')` + `SELECT … FROM Fixture.Partido WHERE Codigo = ?` (P-009, DB-API) | Clase compilada; acta "En Juego" con 1 evento |
| Portal accesible vs. Superserver inaccesible vs. namespace incorrecto vs. objeto inexistente | Capas separadas + sondas | Portal y Superserver se prueban por separado / `NOEXISTE` → `%SYS.Namespace.Exists = 0` / `ObtenerActa('P-999')` → `NO_ENCONTRADO` (404 en la API) |

Hallazgos de IRIS:

* Con un namespace inexistente, `iris.connect` devuelve **"Access Denied"**, el mismo mensaje que con una contraseña errónea. Para separarlos, el diagnóstico reintenta en `IRIS_NAMESPACE_ALTERNATIVO` (`USER`). Si entra, la credencial es válida, y `%SYS.Namespace.Exists` dice si el namespace no existe o si falta permiso (escenario A4e).
* `iris.connect` contra un puerto que no es el Superserver (por ejemplo 52773, el portal) **no respeta su `timeout`**: queda esperando. Lo medimos con un límite por hilo de 6 s. El adaptador de la API y el diagnóstico ponen ese límite por fuera.
* Los logins fallidos cuentan para deshabilitar la cuenta. Por eso no se prueban contraseñas incorrectas contra IRIS.

## 5. Clientes oficiales dentro de los contenedores

[`evidencia/resultados_clientes_contenedor.txt`](evidencia/resultados_clientes_contenedor.txt)
(`scripts/clientes_en_contenedor.sh`). **Origen distinto**: dentro de cada
contenedor, `localhost` es el producto. Confirma que el producto responde a su
cliente oficial, pero **no** prueba el puerto publicado ni el camino de la API.
Las credenciales pasan como variables de entorno (`-e VAR` sin valor), no como
argumentos.

| Producto | Cliente | Comando (resumido) | Resultado |
|---|---|---|---|
| MongoDB | `mongosh` | `ping` + `equipos.findOne({_id:"ARG"})` en `fixture2030` | `ping.ok=1`, 64 equipos, ARG=Argentina |
| Neo4j | `cypher-shell` | `--param 'codigo => "P-001"'` + `MATCH` parametrizado | P-001, 2030-06-10, [ARG, ESP] |
| Cassandra | `cqlsh -k fixture2030` | `SELECT … WHERE id_partido='P-001' AND ventana='203006152015' AND shard=1 LIMIT 3` | 3 filas |
| Redis | `redis-cli` | `PING`, `EXISTS`, `PTTL`, `INFO keyspace` | PONG, 0, -2, `db0:keys=…` |
| InfluxDB | `influxdb3 query` | `COUNT(*)` en la ventana de 15 min (token por `INFLUXDB3_AUTH_TOKEN`) | 1800 |
| IRIS | `iris session IRIS -U USER` | `$SYSTEM.Version.GetNumber()` + `ObtenerActa("P-001")` | 2026.2, acta OK. Entra por el sistema operativo, no por el Superserver |

Ninguno de estos CLI está instalado en la notebook: el modo nativo del
diagnóstico usa los **drivers de Python de la API**, que es lo que exige RNF4
(cliente adecuado por producto, no un HTTP genérico).

## 6. Pruebas de la API (5.5)

`scripts/prueba_api.sh` (módulo `conectividad/api.py`). Solo usa rutas GET.
Cada request lleva su `X-Request-ID` (`h11-<corrida>-<n>`): la API lo devuelve
en la respuesta y lo escribe en cada línea de log de la ruta y del adaptador.
**Antecedente histórico, anterior a la reducción del Hito 10.** Corrida `h11-9f1779`,
2026-10-17 00:33 UTC, API en `127.0.0.1:8000`. La tabla conserva lo observado entonces;
incluye plantel y ficha, eliminados de la API actual. La evaluación vigente usa 17 solicitudes,
con acta P-009 por SQL/DB-API. Ver la nueva evidencia de la API en
`../../fixture2030-hito-10-api-integrada/docs/evidencia/revision_2026-10-19/`.

| Prueba | Método y path | Dependencia | HTTP | ms (cliente) | Clase | Resultado resumido | Líneas de log |
|---|---|---|---|---|---|---|---|
| liveness | `GET /health/live` | — | 200 | 23,4 | éxito | `estado=up` | 1 |
| readiness | `GET /health/ready` | las seis | 200 | 39,2 | éxito | `listo=True estado=up` | 8 |
| diagnóstico | `GET /health/dependencias?refrescar=true` | las seis | 200 | 31,0 | éxito | las seis `up` | 8 |
| CU01 equipo | `GET /equipos/ARG` | mongodb | 200 | 29,7 | éxito | Argentina | 2 |
| CU01 inexistente | `GET /equipos/XYZ` | mongodb | 404 | 4,6 | recurso inexistente | `RECURSO_NO_ENCONTRADO` | 2 |
| CU01 inválido | `GET /equipos/arg` | — | 400 | 24,1 | error de validación | `VALIDACION` (no llega a la base) | 1 |
| CU03 plantel | `GET /equipos/ARG/jugadores?size=5` | mongodb | 200 | 7,6 | éxito | 5 ítems | 3 |
| CU05 ficha | `GET /partidos/P-001` | neo4j + redis | 200 | 33,8 | éxito | P-001 | 4 |
| CU06 eventos | `GET /partidos/P-001/eventos?limit=5` | neo4j | 200 | 27,2 | éxito | 1 evento | 2 |
| CU06 sin eventos | `GET /partidos/P-002/eventos` | neo4j | 200 | 31,1 | respuesta vacía válida | 0 eventos | 2 |
| CU06 inexistente | `GET /partidos/P-999/eventos` | neo4j | 404 | 27,6 | recurso inexistente | `RECURSO_NO_ENCONTRADO` | 2 |
| CU08 muro | `GET /partidos/P-001/comentarios?ventana=203006152015&limit=5` | cassandra | 200 | 43,6 | éxito | 5 ítems | 2 |
| CU08 ventana vacía | `GET /partidos/P-001/comentarios?ventana=203001010000` | cassandra | 200 | 45,1 | respuesta vacía válida | 0 ítems | 2 |
| CU10 sesión | `GET /sesiones/S-0001` | redis | 404 | 4,2 | recurso inexistente | `SESION_NO_VIGENTE` (TTL vencido) | 2 |
| CU12 estadísticas | `GET /partidos/P-001/estadisticas?desde=…20:00Z&hasta=…20:15Z&resolucion=5m` | influxdb | 200 | 45,8 | éxito | 2 series | 2 |
| CU12 sin puntos | `GET …/estadisticas?desde=2031-01-01T00:00Z&hasta=…01:00Z` | influxdb | 200 | 33,6 | respuesta vacía válida | 0 series | 2 |
| CU12 invertido | `GET …/estadisticas?desde=…22:00Z&hasta=…20:00Z` | — | 400 | 23,1 | error de validación | `VALIDACION` | 1 |
| CU13 acta | `GET /partidos-oficiales/P-001` | iris | 200 | 18,5 | éxito | 1 evento | 2 |
| CU13 inexistente | `GET /partidos-oficiales/P-999` | iris | 404 | 4,6 | recurso inexistente | `RECURSO_NO_ENCONTRADO` | 2 |

El tiempo "del cliente" incluye abrir una conexión HTTP nueva desde Python en
Windows, así que varía entre 4 y 46 ms aunque el servidor tarde menos de 5 ms.
No es una medición de rendimiento (Hito 12). El log de acceso registra la
duración en el servidor:
por ejemplo `ruta=/equipos/ARG estado=200 duracion_ms=3.5`, con
`operacion=equipos.find_one resultado=ok duracion_ms=2.0` en el adaptador.

Log asociado a `h11-9f1779-04` ([`evidencia/logs_api_h11.txt`](evidencia/logs_api_h11.txt)):

```
2026-10-17T00:33:09Z INFO [fixture2030.adaptador] request_id=h11-9f1779-04 dependencia=mongodb operacion=equipos.find_one resultado=ok duracion_ms=2.0
2026-10-17T00:33:09Z INFO [fixture2030.acceso] request_id=h11-9f1779-04 metodo=GET ruta=/equipos/ARG estado=200 duracion_ms=3.5
```

**Casos que la prueba distingue (5.5):**

| Caso | Cómo se reconoce | Dónde se observó |
|---|---|---|
| API no alcanzable | Sin respuesta HTTP: `api_no_alcanzable`; las rutas restantes quedan en SKIP | Se clasifica en `api.py`; no ocurrió con la API levantada |
| API alcanzable con dependencia fallida | 503 `DEPENDENCIA_NO_DISPONIBLE` o 504 `DEPENDENCIA_TIMEOUT`, con `detalles[].dependencia` | Fallo controlado y escenarios B1/B2 |
| Recurso inexistente | 404 `RECURSO_NO_ENCONTRADO` / `SESION_NO_VIGENTE` | XYZ, P-999, S-0001 |
| Respuesta vacía válida | 200 con `items`, `eventos` o `series` vacíos | P-002, ventana 203001010000, año 2031 |
| Error de validación | 400 `VALIDACION`; no se consulta ninguna base (sin línea de adaptador en el log) | `arg`, intervalo invertido |
| Operación exitosa | 2xx con datos | El resto |

## Selección de capas y negociación mediante drivers

`--capas lectura` inicializa los recursos necesarios sin presentar capas omitidas
como si se hubieran ejecutado. Cassandra abre una sesión y verifica el contexto
antes de leer. La selección de capas no omite los prerrequisitos de la operación.

Al usar drivers, la negociación de protocolo y el intercambio de identidad pueden
ocurrir en la misma llamada. El resultado lo declara explícitamente; las filas
separadas de protocolo y autenticación no pretenden medir dos handshakes distintos.
Se conserva la prueba TCP independiente y se clasifican los errores del driver.

Las sondas verifican el resultado y la causa: un 200 con token inválido no es OK,
un error de permisos no prueba una database inexistente y un keyspace ausente no
demuestra que se rechazó una partición incompleta. Un `NoHostAvailable` por sí solo
no demuestra un timeout: también puede envolver un rechazo o un error de identidad.

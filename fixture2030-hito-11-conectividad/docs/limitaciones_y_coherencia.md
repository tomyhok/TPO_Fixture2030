# Limitaciones y coherencia con el TPO

Grupo 4 — Ingeniería de Datos II — Fixture 2030

## 1. Limitaciones (RNF17)

**Alcance de los resultados**

* **OK no es rendimiento.** Cada OK dice que una prueba funcionó en un momento y desde un origen. Las latencias son de lecturas mínimas sobre datos de muestra, con un nodo por producto: no permiten estimar operaciones por segundo ni el comportamiento con volumen (Hito 12).
* **Un solo origen principal.** La evaluación principal se hizo desde la notebook (Windows 11, Git Bash). La red de Docker se probó con un contenedor efímero que usa la imagen de la API. La **API en modo contenedor** (`docker-compose.api.yml`, puerto 8001) no estaba levantada: su camino no se probó en este hito. Se puede probar con `API_URL=http://127.0.0.1:8001 bash scripts/prueba_api.sh`.
* **Corrida puntual.** Los datos de muestra cambian con el tiempo: las sesiones de Redis vencen a los 30 minutos y la API crea `cache:partido:*` al leer. Por eso `sesion:S-0001` aparece ausente y `CU10` responde 404 `SESION_NO_VIGENTE`. Para verla presente hay que recargar `fixture2030-redis/scripts/carga_muestra.redis`.

**Herramientas**

* En la notebook **no** están instalados `mongosh`, `cypher-shell`, `cqlsh`, `redis-cli`, `influxdb3` ni `nc`. Se reemplazaron por: (a) los drivers de Python de la API para las pruebas nativas desde el origen real; (b) los CLI oficiales **dentro de cada contenedor** como segunda opinión desde otro origen; (c) `connect()` de Python en lugar de `nc`. Si falta un driver, sus capas quedan en SKIP.
* El portal de IRIS y el Browser de Neo4j se prueban solo por HTTP: no se automatiza un login en esas interfaces web.

**Seguridad del laboratorio (observaciones, no se modificaron)**

* **Credenciales e historial.** Los Compose leen `MONGO_PASSWORD` y `NEO4J_PASSWORD`
  del `.env` raíz, excluido de Git. Los ejemplos ya no publican contraseñas ni URI
  autenticadas. Esto no elimina los valores que aparecieron en commits anteriores:
  siguen expuestos y su rotación debe coordinarse con quienes los usan. La revisión
  no reescribe el historial ni cambia las contraseñas de bases existentes.
  Si una contraseña coincide con un identificador público, la verificación por
  valor sigue siendo inconclusa; se informa esa limitación.

* Cassandra y Redis no tienen autenticación (sesión CQL sin credenciales, usuario Redis `default` sin contraseña): cualquier cliente que alcance el puerto puede operar. Los puertos se publican en `0.0.0.0`; en una red compartida convendría publicarlos solo en `127.0.0.1`.
* Neo4j Community no tiene RBAC (`roles=null`): la capa de autorización solo prueba que la identidad puede abrir una transacción de lectura.
* MongoDB usa el usuario `root`: la autorización pasa, pero no demuestra mínimo privilegio. IRIS sí usa un usuario con rol mínimo (`FixtureAPI`).

**Pruebas que no se hicieron a propósito**

* **Credencial inválida contra IRIS:** los logins fallidos cuentan para deshabilitar la cuenta. Se probó la credencial inválida con MongoDB, que no bloquea cuentas. Para IRIS se separa credencial de namespace sin provocar fallos de login.
* **Firewall o ruta real:** el timeout de red se simuló con una dirección sin ruta (`10.255.255.1`), no con un firewall.
* **Detención de otros productos:** el fallo controlado se hizo con MongoDB, que reinicia en ~2 s. Redis ya se había detenido en el Hito 10 (`09_dependencia_caida.txt`). Cassandra y Neo4j tardan más en arrancar y no aportaban otra clase de falla.

**Particularidades del entorno**

* Windows tarda ~2 s en informar *connection refused* en `127.0.0.1`. Con `TIMEOUT_CONEXION_S=2`, la API puede informar una dependencia detenida como timeout (504) y no como no disponible (503), según el driver. En Linux o dentro de Docker el rechazo es inmediato.
* La salida de la consola de Windows usa cp1252: el diagnóstico fuerza UTF-8.

## 2. Coherencia con el TPO

La evaluación usa los mismos módulos, datos, claves y patrones de acceso de los
hitos anteriores. No hay datos ni consultas inventadas para este hito.

| Hito | Producto | Modelo del hito que la prueba respeta | Prueba del Hito 11 | Ruta de la API |
|---|---|---|---|---|
| 4 | MongoDB | Colecciones `equipos` (`_id` = código ISO) y `jugadores` (`codigo_equipo`), proyecciones y límites | `find_one({_id:'ARG'})` y `count_documents({codigo_equipo:'ARG'}, limit=100)` | `/equipos/ARG` |
| 5 | Neo4j | `(:Equipo)-[:DISPUTA]->(:Partido)`, `(:Evento)-[:CORRESPONDE_A]->`, búsqueda por `codigo_partido` (restricción de unicidad) | `MATCH` parametrizado con `LIMIT`; P-002 sin eventos | `/partidos/P-001/eventos`, `/partidos/P-002/eventos` |
| 6 | Cassandra | Partición `(id_partido, ventana, shard)` con 4 shards, clustering por `timeuuid`, sin `ALLOW FILTERING` | `SELECT` con la partición completa en los 4 shards; la sonda confirma que la partición incompleta se rechaza | `/partidos/P-001/comentarios?ventana=…` |
| 7 | Redis | `sesion:<id>` (Hash, TTL 1800 s), `cache:partido:<codigo>` (TTL 300 s) | `EXISTS/TYPE/PTTL` de `sesion:S-0001`; ausente vs. expirada vs. no disponible | `/sesiones/S-0001` |
| 8 | InfluxDB 3 | `estadisticas_partido` por `partido_id`, ventanas acotadas, `date_bin` con AVG para la posesión | `COUNT` en 15 min + `date_bin(5 min)` con `AVG(posesion_pct)` | `/partidos/P-001/estadisticas` |
| 9 | IRIS | Clases `Fixture.*` con índice único `Codigo`, rol SQL de lectura | `SELECT … FROM Fixture.Partido WHERE Codigo = ?` (P-009, DB-API), `%Dictionary.CompiledClass` | `/partidos-oficiales/P-009` |
| 10 | API | Adaptadores, errores 503/504, request ID, timeouts | Cadena completa cliente → API → adaptador → producto; dos defectos encontrados y corregidos | 17 solicitudes GET de diagnóstico sobre seis lecturas de negocio y salud |

**Base para el Hito 12.** Quedan medidos: desde qué entorno se conecta la API
(`127.0.0.1` y los puertos publicados), qué driver y qué versión usa cada
producto, qué contexto selecciona, cuánto tarda una lectura mínima en frío y en
caliente, cuánto tarda en fallar cada tipo de caída (~2 s en Windows) y que la
API falla de forma acotada e identificable. Para la prueba de carga se
recomienda: precalentar las conexiones (Cassandra tarda ~1,4 s en abrir la
sesión), ejecutar el generador de carga desde el mismo origen que la API o
dentro de la red Docker (para no medir los 2 s del rechazo de Windows) y usar
`/health/dependencias` como monitor durante la carga.

## Entorno observado en la revisión del 19/10/2026

MongoDB, Neo4j y Redis aceptan las lecturas. Cassandra responde pero no tiene el
keyspace `fixture2030`. IRIS tiene clases del Hito 9 anteriores a la fachada
actual: falta `CodigoIndexOpen`. No hay token local disponible de InfluxDB.
Son condiciones de preparación del laboratorio, registradas como falla de contexto
o módulo no configurado, y no se sustituyen por resultados supuestos.

El 23/10/2026 se verificó InfluxDB en la notebook que tiene `.influxdb3-token`: 14 OK y 0 FAIL
([salida](../../fixture2030-influxDB/docs/evidencia/09_conectividad.txt)).

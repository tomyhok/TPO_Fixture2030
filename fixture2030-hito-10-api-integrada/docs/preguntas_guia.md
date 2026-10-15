# Hito 10 — Respuestas a las Preguntas Guía

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Respuestas a la sección 12 del enunciado, con referencia al código o
documento donde se ve cada decisión.

---

**1. ¿Qué problema del Fixture resuelve cada endpoint?**
Cada ruta corresponde a un caso de uso (CU01–CU16) con su consumidor:
ficha y plantel de las selecciones, ficha y eventos de un partido, rivales,
muro y publicación de comentarios, validación y cierre de sesiones,
estadísticas en vivo, acta oficial con su estado y eventos, y disponibilidad
de la plataforma. Ver [`casos_de_uso.md`](casos_de_uso.md), sección 2.

**2. ¿Qué fuente atiende cada operación y por qué?**
La que ya era fuente de verdad del dato en el hito correspondiente: MongoDB
para los documentos de equipos y jugadores, Neo4j para las relaciones del
fixture, Cassandra para los comentarios masivos por partición, Redis para lo
temporal (sesiones, caché, claves de idempotencia), InfluxDB para las series
temporales e IRIS para la entidad compleja con reglas. Ver el mapa en
[`contratos_y_errores.md`](contratos_y_errores.md#2-mapa-de-endpoints).

**3. ¿Qué parte del código conoce el driver específico de cada base?**
Solo `app/adapters/<producto>_adapter.py`. Ningún otro módulo importa
`pymongo`, `neo4j`, `cassandra`, `redis`, `httpx` (InfluxDB) ni `iris`. Las
rutas conocen servicios y los servicios conocen métodos del dominio
(`leer_muro`, `ficha_partido`), no el lenguaje de consulta.

**4. ¿Qué ocurre si el recurso no existe?**
404 `RECURSO_NO_ENCONTRADO` (o `SESION_NO_VIGENTE` para sesiones). Si el
recurso existe pero la consulta no trae resultados, la respuesta es 200 con
lista vacía (por ejemplo P-002 sin eventos).

**5. ¿Qué ocurre si la base está caída?**
503 `DEPENDENCIA_NO_DISPONIBLE` si la conexión se rechaza, 504
`DEPENDENCIA_TIMEOUT` si no responde a tiempo. En los dos casos `detalles`
indica la fuente. La única respuesta degradada es la ficha del partido con
Redis caído: 200 con `X-Cache: BYPASS`, leyendo Neo4j. La API se reconecta
sola cuando la base vuelve ([`evidencia/09_dependencia_caida.txt`](evidencia/09_dependencia_caida.txt)).

**6. ¿Cómo se distingue una respuesta vacía válida de un error de dependencia?**
La lista vacía solo se arma cuando el driver devolvió un resultado. Si el
driver lanza una excepción, el adaptador la traduce a 503/504 y la ruta nunca
llega a construir un 200. En Redis, `nil` / `TTL -2` es "no existe" y una
excepción de conexión es "no disponible". En InfluxDB, `HTTP 200 []` es "sin
puntos" y un 401/404 de la fuente es "no disponible".

**7. ¿Qué parámetros deben validarse antes de consultar?**
Todos: formatos de los códigos (`^P-\d{3}$`...), enums, rangos de `page`,
`size` y `limit`, ventana `AAAAMMDDHHMM` válida, cursor timeuuid, fechas con
zona, orden y amplitud del intervalo, cuerpos sin campos extra y la
`Idempotency-Key`. Ver la tabla en [`contratos_y_errores.md`](contratos_y_errores.md#3-validación-rf10-rnf3).
Las pruebas verifican que un 400 no llama a ningún adaptador.

**8. ¿Qué límites o paginación se aplican a las respuestas grandes?**
`size` ≤ 50 con `page` (MongoDB), `limit` ≤ 200 eventos y ≤ 20 rivales con
`LIMIT` en Cypher (Neo4j), `limit` ≤ 100 por ventana de 1 minuto con cursor
(Cassandra), ventana ≤ 3 h con agregación obligatoria y `LIMIT` de 1.081
puntos por equipo (InfluxDB).

**9. ¿Qué endpoint modifica datos y cómo se comporta si se repite?**
`POST /partidos/{c}/comentarios` y `POST /partidos-oficiales/{c}/eventos`
(creación: con la misma clave devuelven el mismo resultado, sin duplicar),
`PATCH /partidos-oficiales/{c}/estado` (pedir el estado actual responde
`cambiado: false`) y `DELETE /sesiones/{id}` (siempre 204).

**10. ¿Cómo se protege una operación de escritura frente a reintentos o duplicados?**
Con `Idempotency-Key` obligatoria, reservada con `SET NX EX` en Redis junto
con la huella del cuerpo. La clave se libera si la escritura falla y guarda
la respuesta si tiene éxito. Ver
[`contratos_y_errores.md`](contratos_y_errores.md#5-idempotencia-y-operaciones-de-escritura-rf19-rnf14).

**11. ¿Qué diferencia hay entre consultar Neo4j mediante una relación y consultar Cassandra mediante una partición?**
En Neo4j se parte de un nodo encontrado por su restricción única y se
**recorren relaciones** (`CORRESPONDE_A`, `PROTAGONIZA`), con profundidad
variable y sin saber de antemano dónde están los datos. En Cassandra no hay
relaciones: hay que conocer la **clave de partición completa**
`(id_partido, ventana, shard)` para que la lectura vaya a un nodo y lea filas
contiguas ya ordenadas por `id_comentario`. Por eso el muro pide `ventana` y
lee los 4 shards, en lugar de "todos los comentarios del partido".

**12. ¿Qué diferencia hay entre una clave Redis inexistente y Redis no disponible?**
La clave inexistente es una respuesta normal de Redis (`HMGET` → nils,
`TTL` → -2) y produce 404 `SESION_NO_VIGENTE`. Redis no disponible es una
excepción del cliente (`ConnectionError` o `TimeoutError`) y produce 503/504.

**13. ¿Qué intervalo temporal acepta el endpoint de InfluxDB?**
`[desde, hasta)` en ISO 8601 con zona horaria, con `desde < hasta` y una
amplitud máxima de 3 horas (un partido con alargue y margen). La resolución
es 10s, 1m o 5m.

**14. ¿Qué namespace y entidad utiliza el adaptador IRIS?**
Namespace `USER` (configurable con `IRIS_NAMESPACE`). Usa las clases
`Fixture.Partido` (por el índice único `Codigo`), `Fixture.Evento` y
`Fixture.Arbitro` a través de la fachada `Fixture.API`.

**15. ¿Cómo se configura cada host y puerto sin modificar el código?**
Con variables de entorno o `.env` (ver
[`conectividad_y_configuracion.md`](conectividad_y_configuracion.md#2-hosts-y-puertos)).
El modo contenedor cambia los hosts por los nombres de servicio solo con
variables del compose.

**16. ¿Qué información se registra en los logs y qué información se omite?**
Se registran request ID, método, ruta, estado, dependencia, operación,
resultado y duración. Se omiten cuerpos, query strings, credenciales,
consultas y datos de sesión. Ver
[`conectividad_y_configuracion.md`](conectividad_y_configuracion.md#6-logs-rnf10-y-seguridad).

**17. ¿Cómo se verifica que OpenAPI describe el comportamiento real?**
El YAML se genera del código. `test_contrato_openapi.py` compara el archivo
con la aplicación, y las pruebas de integración verifican que cada código
devuelto esté declarado para su operación. La evidencia 13 compara el
`openapi.json` servido con el YAML versionado.

**18. ¿Qué prueba ejecutaría el equipo si una dependencia responde lentamente?**
`test_fuente_lenta_corta_por_timeout`: levanta un servidor TCP que acepta la
conexión y nunca responde, apunta la API a él con timeouts de 1 s y verifica
que responde 503/504 en menos de 5 s. Para lentitud parcial (responde, pero
tarde) se bajaría `TIMEOUT_OPERACION_S` y se mediría con
`scripts/medir_latencia.py`.

**19. ¿Qué parte de la API podría cachearse y qué riesgo de frescura tendría?**
Ya se cachea la ficha del partido (TTL 300 s): un gol cargado en Neo4j puede
tardar hasta 5 minutos en verse. Se podría cachear la ficha de la selección
(`cache:equipo:<iso>` del Hito 7, TTL 1 h, porque cambia muy poco) y los
resúmenes de partidos finalizados de InfluxDB (no cambian). **No** conviene
cachear el muro de comentarios (ya se lee por partición y cambia cada
segundo), las sesiones (Redis ya es la fuente) ni el acta (la mesa de control
necesita el estado actual para validar transiciones).

**20. ¿Qué limitaciones del laboratorio impiden afirmar que la API está lista para millones de usuarios?**
Cada base es un único nodo sin réplicas en una notebook, con CPU y memoria
compartidas. La API corre con un solo proceso de uvicorn, sin balanceador.
Solo se midió latencia secuencial, sin carga concurrente ni throughput. No hay
autenticación, límites de tasa ni TLS. El conector IRIS usa una conexión
serializada. Las escrituras con BATCH logged tienen un costo extra que no se
midió a escala. Los volúmenes son de laboratorio. Faltan pruebas de carga,
réplicas y monitoreo (próximos hitos).

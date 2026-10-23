> Evidencia histórica de la entrega previa. Para las correcciones docentes consultar [`revision_2026-10-19/`](revision_2026-10-19/README.md) (API) y la [verificación vigente de InfluxDB](../../../fixture2030-influxDB/docs/evidencia/README.md#verificación-vigente-23102026). No atribuir estos resultados al código modificado.

# Evidencia del Hito 10

Todos los archivos se generaron con `bash scripts/generar_evidencia.sh --con-caida`,
con la API levantada en la notebook (`scripts/iniciar_api.sh`) y las bases del
`docker-compose.yml` raíz preparadas con `scripts/preparar_datos.sh`. Cada
archivo indica la fecha (UTC) y, para cada escenario, el comando cURL exacto,
el estado HTTP, los headers relevantes y el cuerpo. No contienen credenciales.

| Archivo | Contenido | Requisitos |
|---|---|---|
| `00_ambiente.txt` | Commit, sistema, Python, Docker, contenedores y versiones de dependencias | RNF11, RNF18 |
| `01_conectividad.txt` | Estado de los contenedores, ping a cada fuente con los adaptadores, `/health` | RF17, 5.13 |
| `02_mongodb.txt` | CU01–CU04: ficha, 404, paginación con filtro, página vacía, plantel por posición, jugador | RF3 |
| `03_neo4j.txt` | CU05–CU07: caché MISS → HIT con TTL, 404, eventos con protagonista, partido sin eventos, rivales | RF4 |
| `04_cassandra.txt` | CU08–CU09: muro paginado con cursor, ventana vacía, alta 201, reintento 200 sin duplicar, 409, 404 y verificación directa en la tabla | RF5, RF19 |
| `05_redis.txt` | CU10–CU11: sesión vigente sin datos internos, sesión que expira, cierre idempotente | RF6 |
| `06_influxdb.txt` | CU12: ventanas a 5m y 1m, tope de puntos, ventana vacía, intervalos inválidos | RF7 |
| `07_iris.txt` | CU13–CU15: acta, 404, transición inválida 409, transición válida e idempotente, evento 201/200, 409 por `%OnBeforeSave`, 400 | RF8, RF19 |
| `08_validacion_y_errores.txt` | 400 por ruta, query, cuerpo y header; 404 de ruta; 405; reutilización de `X-Request-ID` | RF10–RF12 |
| `09_dependencia_caida.txt` | `docker stop fixture2030-redis`: 504 en sesión, ficha degradada `BYPASS`, escritura rechazada, `/health` 503, recuperación tras `docker start` | RF15, RNF9 |
| `10_logs_correlacion.txt` | Líneas de `logs/api.log` de dos requests con `X-Request-ID` propio (ruta, adaptadores, resultado, duración) y búsqueda de secretos | RF18, RNF10 |
| `11_pruebas.txt` | Salida de `pytest -v`: 157 pruebas (122 unitarias, 35 de integración) | RF15, 5.12 |
| `12_latencia.md` | Medición de latencia con método, entorno, volumen, configuración y limitaciones | RNF18 |
| `13_contrato.txt` | Swagger UI disponible, `openapi.json` servido idéntico a `openapi/openapi.yaml`, códigos por operación | RF13, RNF2 |
| `14_modo_contenedor.txt` | API en contenedor (`docker-compose.api.yml`) contra las bases por nombre de servicio | 5.13 |
| `15_postman_newman.txt` | Corrida de la colección Postman con Newman: 64 requests, 264 aserciones | RF14 |

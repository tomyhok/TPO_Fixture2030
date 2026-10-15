# Medición básica de latencia (RNF18)

- **Fecha (UTC):** 2026-10-15 18:55:26
- **Método:** 200 requests HTTP secuenciales por escenario (1 cliente, sin concurrencia), 10 de calentamiento descartadas. Latencia medida en el cliente (`time.perf_counter`).
- **Entorno:** Windows 11, 16 CPU lógicas, Python 3.12.10, Docker Engine 29.7.2 (Docker Desktop). API con uvicorn (1 worker) en la notebook; las seis bases en contenedores del `docker-compose.yml` raíz.
- **Volumen de datos:** 64 selecciones y 1.472 jugadores (MongoDB); grafo del Hito 5; muestra de 35 comentarios del Hito 6 más los creados por las pruebas; 28.800 puntos de P-001/P-002 en InfluxDB (además de los del Hito 8); 3 actas en IRIS.
- **Configuración:** timeouts de conexión 2 s y de operación 5 s; nivel de log INFO.

| Fuente | Escenario | Respuestas | p50 (ms) | p95 (ms) | p99 (ms) | máx (ms) |
|---|---|---|---:|---:|---:|---:|
| MongoDB | GET /equipos/{codigo} | 200×200 | 2.9 | 5.8 | 6.3 | 6.7 |
| MongoDB | GET /equipos?size=10 | 200×200 | 3.9 | 5.7 | 6.8 | 7.2 |
| Neo4j | GET /partidos/{c}/eventos | 200×200 | 6.4 | 8.3 | 8.9 | 10.9 |
| Redis+Neo4j | GET /partidos/{c} (cache HIT) | 200×200 | 2.3 | 3.8 | 4.3 | 4.8 |
| Cassandra | GET /partidos/{c}/comentarios | 200×200 | 15.6 | 17.7 | 18.2 | 18.6 |
| Redis | GET /sesiones/{id} (404) | 404×200 | 2.2 | 3.5 | 4.6 | 5.4 |
| InfluxDB | GET /estadisticas 30 min @1m | 200×200 | 15.2 | 19.3 | 22.1 | 30.6 |
| InfluxDB | GET /estadisticas 3 h @10s | 200×200 | 30.3 | 34.3 | 68.3 | 74.2 |
| IRIS | GET /partidos-oficiales/{c} | 200×200 | 2.3 | 3.3 | 4.7 | 7.0 |
| Validación | GET /equipos/arg (400) | 400×200 | 1.1 | 1.5 | 2.1 | 2.7 |

**Limitaciones.** Un solo cliente secuencial no mide throughput ni comportamiento bajo carga concurrente; todas las bases comparten CPU y memoria de la notebook con la API; cada base es un nodo único sin réplicas; los volúmenes son de laboratorio. Las cifras sirven para comparar escenarios entre sí en este entorno, no para dimensionar producción.

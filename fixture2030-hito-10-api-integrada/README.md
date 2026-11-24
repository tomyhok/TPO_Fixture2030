# Grupo 4 — Hito 10: API REST integrada

La API integra los seis motores con **seis lecturas representativas**, una por motor.
Se priorizan contratos, validación, errores y pruebas esenciales, siguiendo la devolución docente.
Los endpoints de salud ampliados se conservan por los requisitos del Hito 11.

## Ejecutar

1. Levantar los motores desde la raíz: `docker compose up -d`.
2. En esta carpeta, crear un entorno Python 3.12 e instalar `pip install -r requirements.txt`.
3. Copiar `.env.example` a `.env` y completar las credenciales del laboratorio. No se versiona.
4. Preparar las muestras de los hitos 4–9. `bash scripts/preparar_datos.sh` reutiliza sus scripts;
   no borra datos, pero vuelve a escribir las muestras con identificadores conocidos. No ejecutar
   para conservar cambios manuales hechos sobre esos mismos identificadores.
5. Ejecutar `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Abrir `http://127.0.0.1:8000/docs`.

El token de InfluxDB no hace falta escribirlo en el `.env`. Con `INFLUX_TOKEN` vacío, la API lo lee
de `fixture2030-influxDB/.influxdb3-token`, que genera el Hito 8 y no se versiona. Si faltan los dos,
el diagnóstico informa `not_configured` y la lectura de estadísticas responde 503. En ese caso hay
que recuperar el archivo; no generar otro token ni reinicializar el almacenamiento. El 23/10/2026 se
verificó con ese archivo: `test_lectura_real[influxdb]` pasó e InfluxDB figuró `up`
([evidencia en el Hito 8](../fixture2030-influxDB/docs/evidencia/README.md#verificación-vigente-23102026)).

## Alcance actual

| Lectura | Fuente y responsabilidad |
|---|---|
| `GET /equipos/{codigo_iso}` | MongoDB: ficha de una selección |
| `GET /partidos/{codigo_partido}/eventos?limit=5` | Neo4j: eventos y protagonista, recorrido acotado |
| `GET /partidos/{codigo_partido}/comentarios?ventana=203006152015&limit=5` | Cassandra: muro de una ventana |
| `GET /sesiones/{id_sesion}` | Redis: datos públicos y TTL; sin renovación |
| `GET /partidos/{codigo_partido}/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z` | InfluxDB: agregado temporal |
| `GET /partidos-oficiales/{codigo_partido}` | IRIS: SELECT de la proyección de objetos |

La demostración del Hito 9 crea el acta `P-009`. Los demás motores usan `P-001`.
Cada ruta consulta exclusivamente su fuente. No hay caché Redis sobre Neo4j, escrituras HTTP,
coordinación de escrituras entre motores, reservas de idempotencia ni fachada ObjectScript.

Salud: `/health` verifica las seis fuentes; `/health/live` no consulta bases;
`/health/ready` permite servicio parcial; `/health/dependencias` detalla cada fuente y reutiliza
el chequeo durante un TTL configurable. Esta reutilización es del diagnóstico en memoria,
no una caché Redis de datos del negocio.

## Portal del Fixture y front de integración

Con la API levantada, `http://localhost:8000/` redirige al **portal** (`/portal/`). Son
páginas estáticas sin dependencias (`app/front/portal/` y `app/front/demo/`) servidas por la
misma API. Las banderas de `app/front/portal/img/banderas/` son de
[flag-icons](https://github.com/lipis/flag-icons) 7.2.3 (licencia MIT, copiada junto a los archivos).

**Portal (`/portal/`)**: simula la página pública del Mundial 2030.

| Pantalla / acción | Fuente |
|---|---|
| Fixture de partidos (filtros por grupo y estado), estado y marcador | Neo4j (`Partido.estado`, `DISPUTA`, `SE_JUEGA_EN`, `DIRIGE`, `DEL_GRUPO`, goles de `Evento`), en una sola consulta |
| Posiciones de la fase de grupos | Neo4j (resultados de los partidos finalizados) + MongoDB (selecciones de cada grupo); se calculan en el portal |
| Grupos, selecciones (con buscador) y planteles | MongoDB (`equipos`, `jugadores`) |
| Ingresar / salir | Redis: crea y borra `sesion:S-5xxx` (hash + TTL 30 min) |
| Muro en vivo: leer y publicar | Cassandra: escritura doble `comentarios_por_partido` + `comentarios_por_usuario`; lee las últimas 15 ventanas de 1 minuto |
| Visitas y conectados | Redis: `contador:partido:<p>:visitas` y set `conectados:partido:<p>` |
| Estadísticas y gráfico de posesión | InfluxDB (ruta `/partidos/{p}/estadisticas`) |
| Cronología | Neo4j (`Evento`) |
| Control de la demo: iniciar o finalizar un partido | Neo4j: `SET p.estado`, solo hacia adelante (`Programado` → `En Juego` → `Finalizado`); 409 si se intenta volver atrás |
| Simulación en tiempo real al iniciar un partido programado | Neo4j (goles y tarjetas como `Evento`, estado final), InfluxDB (un punto por minuto de juego), Cassandra (relator e hinchada simulada en el muro), Redis (reloj `reloj:partido:<p>`) |
| Identidad del usuario | MongoDB `usuarios_portal`: el mismo alias recupera el mismo `usuario_id` al volver a ingresar |
| Prode: pronosticar, resumen del partido, mis pronósticos, tabla de posiciones | MongoDB (`predicciones`, `liquidaciones`, `tabla_posiciones`); Neo4j aporta el estado del partido y los goles |

Las rutas que usa el portal están bajo `/portal/api` y quedan **fuera del contrato OpenAPI**
público, que tiene solo las cinco lecturas (una por motor). Las escrituras exigen una sesión
vigente en el header `X-Sesion-ID` (401 `SESION_REQUERIDA` si falta o venció). Errores:
400 si el equipo no juega el partido; el minuto de cada comentario lo pone la API con el reloj de la simulación.

### Prode (MongoDB)

Cada usuario pronostica el marcador de un partido: **3 puntos** por el resultado exacto y
**1 punto** por acertar el ganador o el empate. A igualdad de puntos desempata la cantidad de plenos.

| Ruta | Qué hace |
|---|---|
| `PUT /portal/api/partidos/{p}/prediccion` | Crea o corrige el pronóstico (`goles_local`, `goles_visitante`, 0–20). 409 `PREDICCION_CERRADA` si el partido no está `Programado` o ya se puntuó |
| `GET /portal/api/partidos/{p}/predicciones` | Reparto local/empate/visitante, marcadores más elegidos, el pronóstico propio y el resultado puntuado |
| `GET /portal/api/predicciones` | Pronósticos del usuario con sus puntos |
| `GET /portal/api/posiciones?equipo=ARG&limit=50` | Tabla general o de una hinchada (selección favorita), con la fila del usuario |

Colecciones, creadas con `$jsonSchema` estricto e índices la primera vez que se usan:

| Colección | `_id` | Contenido |
|---|---|---|
| `usuarios_portal` | alias en minúsculas | `usuario_id` (índice único), alias, selección favorita |
| `predicciones` | `<partido>:<usuario>` (una por usuario y partido) | marcador, resultado `L/E/V`, `puntos` y `acierto` (null hasta puntuar) |
| `liquidaciones` | código de partido | marcador con el que se puntuó |
| `tabla_posiciones` | `usuario_id` | vista materializada con `$group` + `$lookup` + `$merge`; la posición se calcula con `$setWindowFields`/`$rank` |

**Puntuación.** Cuando el partido pasa a `Finalizado` en Neo4j, la próxima consulta de la tabla, de
"mis pronósticos" o del resumen del partido puntúa las predicciones pendientes con un `update_many`
por pipeline (el cálculo lo hace MongoDB) y rehace la tabla. Es idempotente: no vuelve a puntuar lo
ya puntuado. El marcador sale de los eventos `Gol` de Neo4j, con el mismo criterio que muestra el
portal. Si Neo4j no responde, la tabla se sirve igual y el partido figura en `pendientes`.
Para probarlo: pronosticar P-002 con uno o más usuarios y, con una sesión iniciada, usar
"Iniciar partido" en la página del partido.

### Simulación de un partido

"Iniciar partido" sobre un partido `Programado` lo pasa a `En Juego` y arranca un hilo en la API
(`app/services/simulador_service.py`) que juega los 90 minutos más el descuento en
`SIMULACION_DURACION_S` segundos reales (60 por defecto). Cada minuto de juego puede haber gol
(≈3 por partido, más probable de delanteros), amarilla (la segunda es roja) o roja directa, con
jugadores reales del plantel en Neo4j. Además comenta una hinchada simulada de 24 usuarios
(`U-9001` a `U-9024`, mitad por selección): charla según quién domina la pelota, festejos y
lamentos con cada gol, reacciones a las expulsiones, entretiempo y final. Son ~100 comentarios por
partido con la misma doble escritura del muro, repartidos entre los 4 shards. El portal consulta el reloj cada segundo y actualiza
marcador, cronología, estadísticas y muro; al final el partido queda `Finalizado` y el prode lo
puntúa. Si una base falla durante la simulación se registra y el partido sigue; si la API se
detiene, el reloj vence a los 15 s y el partido queda `En Juego`.

Las estadísticas se escriben con marca de tiempo `inicio + minuto de juego` (la hora real de
inicio queda en `p.inicio`), así no se mezclan con la muestra del Hito 8 y el gráfico queda en
minutos de partido. Se escriben con `no_sync`: sin eso InfluxDB tarda ~1 s por escritura.

`scripts/reiniciar_demo.py` deja la demo como al principio para volver a presentarla: borra los
eventos simulados, vuelve P-001 a `En Juego` y todos los demás partidos a `Programado`, borra los
relojes y reabre el prode (todas las predicciones quedan pendientes). Lo usan también
`scripts/reiniciar_muestra.ps1` y `scripts/preparar_datos.sh`.

### Fase de grupos

`scripts/datos/cargar_fase_grupos.py` carga en Neo4j los 96 partidos de la fase de grupos
(P-003 a P-098): todos contra todos en los 16 grupos de 4 de `equipos.json` (la misma fuente de
MongoDB), en tres fechas entre el 11 y el 26 de junio de 2030, con 12 sedes de los países
anfitriones y 12 árbitros de nombre ficticio. Agrega `(:Grupo)`, `(Equipo)-[:INTEGRA]->(Grupo)` y
`(Partido)-[:DEL_GRUPO]->(Grupo)`. Es idempotente y no cambia el estado de partidos ya jugados.
P-001 y P-002 quedan como muestra de los hitos anteriores: enfrentan selecciones de grupos
distintos. Cualquier partido programado se puede simular desde su página.

Es una demo sin contraseña: quien conoce un alias puede ingresar como ese usuario.

**Integración (`/demo/`)**: recorre las cinco bases para un partido y muestra qué clave de
negocio (`codigo_partido`, `codigo_iso`, `id_usuario`) lleva de una base a la siguiente, con
estado HTTP, latencia y `X-Request-ID` de cada consulta.

## Contratos, validación y pruebas

OpenAPI: `openapi/openapi.yaml`, regenerado con `python scripts/exportar_openapi.py`.
Entradas inválidas devuelven 400 antes de acceder a una fuente; ausencias individuales 404;
colecciones vacías 200; dependencia inaccesible 503; timeout 504. Errores internos 500 sin
credenciales, hosts ni trazas en la respuesta. `X-Request-ID` permite relacionar respuesta y log.

`python -m pytest tests/unit -q` ejecuta las pruebas esenciales y las regresiones de salud.
`python -m pytest tests/integration/test_dependencias_caidas.py -q` verifica caídas y timeouts
con clientes reales, sin detener contenedores. La integración positiva completa necesita las
seis fuentes configuradas; su salto no equivale a éxito. Postman contiene 10 solicitudes de lectura.

Evidencia vigente: [revisión de octubre](docs/evidencia/revision_2026-10-19/README.md).
Los archivos anteriores en `docs/evidencia/` describen la API ampliada previa y se conservan
como antecedentes, no como prueba de los endpoints actuales.

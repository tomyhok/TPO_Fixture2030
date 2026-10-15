# Hito 10 — Casos de Uso de la API REST Integrada

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre el apartado **Casos de uso** de la sección 8 del enunciado
(RF2) y la sección 5.1. Los casos de uso se definieron **antes** que las rutas:
cada endpoint de la API existe porque resuelve uno de estos casos, y cada caso
reutiliza un patrón de acceso que ya fue diseñado en el hito del módulo
correspondiente (Hitos 4 a 9). La API no agrega consultas nuevas sobre las
bases: expone por HTTP las que ya están modeladas e indexadas.

---

## 1. Consumidores

| Consumidor | Descripción | Casos que usa |
|---|---|---|
| **App del hincha** | Web y móvil que muestran selecciones, partidos, comentarios y estadísticas en vivo | CU01–CU09, CU12 |
| **Gestor de sesiones** | Componente de la app que valida y cierra la sesión del usuario en cada petición | CU10, CU11 |
| **Mesa de control del partido** | Operador oficial que registra el acta (estado y eventos) del partido | CU13–CU15 |
| **Equipo de operación** | Monitorea la disponibilidad de la plataforma y sus dependencias | CU16 |

No se implementa autenticación de usuarios en este hito: la API corre en el
laboratorio local y ninguna ruta exige credenciales. La sesión se consulta como
un recurso (CU10), igual que en el Hito 7.

## 2. Mapa de casos de uso y endpoints

| CU | Caso de uso | Método y ruta | Fuente(s) | Operación | Prioridad |
|---|---|---|---|---|---|
| CU01 | Ver la ficha de una selección | `GET /equipos/{codigo_iso}` | MongoDB | Lectura | Alta |
| CU02 | Listar selecciones por ranking | `GET /equipos` | MongoDB | Lectura paginada | Alta |
| CU03 | Ver el plantel de una selección | `GET /equipos/{codigo_iso}/jugadores` | MongoDB | Lectura paginada | Alta |
| CU04 | Ver la ficha de un jugador | `GET /jugadores/{id_jugador}` | MongoDB | Lectura | Media |
| CU05 | Ver la ficha de un partido | `GET /partidos/{codigo_partido}` | Redis (caché) + Neo4j | Lectura | Alta |
| CU06 | Ver los eventos de un partido | `GET /partidos/{codigo_partido}/eventos` | Neo4j | Lectura limitada | Alta |
| CU07 | Ver los rivales de una selección | `GET /equipos/{codigo_iso}/rivales` | Neo4j | Lectura limitada | Media |
| CU08 | Leer el muro de comentarios de un partido | `GET /partidos/{codigo_partido}/comentarios` | Cassandra | Lectura por partición con cursor | Alta |
| CU09 | Publicar un comentario | `POST /partidos/{codigo_partido}/comentarios` | Cassandra + Neo4j + Redis | Creación | Alta |
| CU10 | Validar una sesión | `GET /sesiones/{id_sesion}` | Redis | Lectura | Alta |
| CU11 | Cerrar una sesión | `DELETE /sesiones/{id_sesion}` | Redis | Invalidación | Media |
| CU12 | Ver estadísticas en vivo de un partido | `GET /partidos/{codigo_partido}/estadisticas` | InfluxDB | Lectura por ventana temporal | Alta |
| CU13 | Ver el acta oficial de un partido | `GET /partidos-oficiales/{codigo_partido}` | IRIS | Lectura | Alta |
| CU14 | Cambiar el estado de un partido oficial | `PATCH /partidos-oficiales/{codigo_partido}/estado` | IRIS | Actualización validada | Alta |
| CU15 | Registrar un evento en el acta | `POST /partidos-oficiales/{codigo_partido}/eventos` | IRIS + Redis | Creación validada | Media |
| CU16 | Verificar la disponibilidad de las fuentes | `GET /health` | Las seis | Lectura | Alta |

**Por qué hay dos recursos de partido.** `/partidos` (Neo4j) es el **fixture**:
quién juega, dónde y qué relaciones tiene el partido con equipos, sedes y
jugadores. `/partidos-oficiales` (IRIS) es el **acta**: la entidad compleja con
árbitro, estado y eventos validados por reglas de dominio (Hito 9). Las dos
fuentes comparten el código de negocio `P-001`, pero resuelven necesidades
distintas y no se mezclan en una sola respuesta.

## 3. Criterios comunes a todos los casos

Estos criterios se aplican a todos los casos y no se repiten en cada ficha. El
detalle completo del contrato está en `contratos_y_errores.md` y en
`openapi/openapi.yaml`.

**Formato de error único** (RF12, RNF4). Nunca incluye consultas, trazas,
hosts ni credenciales:

```json
{
  "error": {
    "codigo": "RECURSO_NO_ENCONTRADO",
    "mensaje": "No existe la selección 'XYZ'.",
    "request_id": "7f3c1a2e-0b4d-4c55-9a51-2f0f3c9e8d10",
    "detalles": []
  }
}
```

| Situación (sección 5.11) | HTTP | `codigo` |
|---|---|---|
| Parámetro ausente o con formato incorrecto | 400 | `VALIDACION` |
| Recurso inexistente | 404 | `RECURSO_NO_ENCONTRADO` |
| Ruta inexistente o método no permitido | 404 / 405 | `RECURSO_NO_ENCONTRADO` / `METODO_NO_PERMITIDO` |
| Sesión ausente o expirada | 404 | `SESION_NO_VIGENTE` |
| Conflicto de negocio (estado no permite la operación) | 409 | `CONFLICTO_ESTADO` |
| Clave de idempotencia reutilizada con otro cuerpo o en curso | 409 | `CONFLICTO_IDEMPOTENCIA` |
| Dependencia caída o que rechaza la conexión | 503 | `DEPENDENCIA_NO_DISPONIBLE` |
| Dependencia que no responde dentro del timeout | 504 | `DEPENDENCIA_TIMEOUT` |
| Error inesperado | 500 | `ERROR_INTERNO` |

- **Validación antes de consultar** (RF10, RNF3). La validación de ruta, query
  y cuerpo ocurre en la capa HTTP (FastAPI + Pydantic) y las reglas que
  combinan parámetros (orden de fechas, ventana válida, cursor) al inicio del
  servicio, siempre antes de llamar a un adaptador. Una petición que da 400 no
  abre ninguna conexión contra una base.
- **Nunca un 200 para ocultar una falla.** Una lista vacía solo se devuelve
  cuando la fuente respondió correctamente y no hay datos. Si la fuente falló,
  la respuesta es 503 o 504.
- **Request ID** (RF18). Cada respuesta lleva el header `X-Request-ID`. Si el
  cliente lo envía, se reutiliza; si no, la API genera un UUID. El mismo valor
  aparece en el cuerpo de error y en cada línea de log de la ruta y del
  adaptador.
- **Timeouts** (RNF8, RNF9). Cada adaptador define un timeout de conexión y uno
  de operación, configurables por variable de entorno. Agotarlos produce 504,
  nunca una espera indefinida.
- **Códigos de negocio homologados.** Los identificadores son los mismos en
  todos los módulos: `ARG` para selecciones, `ARG-10` para jugadores y `P-001`
  para partidos.

### Formatos de los parámetros

| Parámetro | Regla |
|---|---|
| `codigo_iso` | 3 letras mayúsculas (`^[A-Z]{3}$`) |
| `id_jugador` | `^[A-Z]{3}-\d{1,2}$` (ej. `ARG-10`) |
| `codigo_partido` | `^P-\d{3}$` (ej. `P-001`) |
| `id_sesion` | `^S-\d{4,}$` (ej. `S-0001`) |
| `page` | entero ≥ 1, por defecto 1 |
| `size` / `limit` | entero entre 1 y el máximo indicado en cada caso |
| fechas | ISO 8601 en UTC (`2030-06-10T20:00:00Z`) |

---

## 4. Fichas de casos de uso

Cada ficha responde los puntos de la sección 5.1 y agrega el patrón de acceso
del hito de origen (RNF13) y la validación previa (RF10).

### CU01 — Ver la ficha de una selección

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, al abrir la página de una selección |
| Recibe / envía | Recibe el código de la selección. Envía nombre, confederación, grupo, ranking FIFA, director técnico y si es país anfitrión |
| Fuente | MongoDB, colección `equipos` (Hito 4) |
| Entrada necesaria | `codigo_iso` en la ruta |
| Validación previa | `codigo_iso` cumple `^[A-Z]{3}$`. Si no, 400 sin consultar |
| Patrón de acceso | `findOne({_id: codigo_iso})` con proyección explícita. Usa el índice de `_id` |
| Respuesta esperada | 200 con el documento proyectado. No se devuelve el documento interno completo |
| Si el dato no existe | 404 `RECURSO_NO_ENCONTRADO` |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura |
| Criterio de éxito | 200 con `codigo_iso` igual al pedido y los seis campos del contrato |

### CU02 — Listar selecciones por ranking

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en la tabla general de selecciones |
| Recibe / envía | Recibe filtros y página. Envía una página de selecciones con `codigo_iso`, `nombre`, `confederacion`, `grupo` y `ranking_fifa`, más los metadatos de paginación |
| Fuente | MongoDB, colección `equipos` |
| Entrada necesaria | Query opcional: `confederacion`, `grupo`, `page` y `size` |
| Validación previa | `confederacion` ∈ {CONMEBOL, UEFA, CAF, AFC, CONCACAF, OFC}. `grupo` ∈ A..P. `size` entre 1 y 50 (por defecto 10) |
| Patrón de acceso | `find(filtro).sort({ranking_fifa: 1}).skip().limit()` con los índices `idx_ranking`, `idx_confederacion` e `idx_grupo` (consulta 4 de `02-consultas.js`) |
| Respuesta esperada | 200 con `{ "items": [...], "page": 1, "size": 10, "total": 48 }` |
| Si el dato no existe | Si ninguna selección cumple el filtro, 200 con `items: []` y `total: 0`. Es una respuesta vacía válida |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura paginada (RNF12) |
| Criterio de éxito | Los resultados están ordenados por ranking, cumplen el filtro y no superan `size` |

### CU03 — Ver el plantel de una selección

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en la pestaña "Plantel" de una selección |
| Recibe / envía | Recibe la selección y, opcionalmente, una posición. Envía `id_jugador`, `nombre`, `dorsal`, `posicion` y `club_actual` |
| Fuente | MongoDB, colecciones `equipos` y `jugadores` |
| Entrada necesaria | `codigo_iso` en la ruta. Query opcional: `posicion`, `page` y `size` |
| Validación previa | `codigo_iso` con formato válido. `posicion` ∈ {ARQ, DEF, MED, DEL}. `size` entre 1 y 50 (por defecto 26) |
| Patrón de acceso | Primero verifica que la selección exista (`equipos` por `_id`). Después busca `jugadores` por `{codigo_equipo, posicion}` con el índice `idx_equipo_posicion`, ordena por dorsal y proyecta solo los campos del contrato (consulta 3 de `02-consultas.js`) |
| Respuesta esperada | 200 con la página de jugadores |
| Si el dato no existe | Selección inexistente: 404. Selección existente sin jugadores en esa posición: 200 con `items: []` |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura paginada |
| Criterio de éxito | Todos los jugadores devueltos tienen `codigo_equipo` igual al pedido |

### CU04 — Ver la ficha de un jugador

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, al tocar un jugador del plantel o de un evento |
| Recibe / envía | Recibe `id_jugador`. Envía nombre, dorsal, posición, fecha de nacimiento, edad, altura, pie hábil, club y selección |
| Fuente | MongoDB, colección `jugadores` |
| Entrada necesaria | `id_jugador` en la ruta |
| Validación previa | Formato `^[A-Z]{3}-\d{1,2}$` |
| Patrón de acceso | `findOne({_id})` con proyección |
| Respuesta esperada | 200 con la ficha |
| Si el dato no existe | 404 |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura |
| Criterio de éxito | 200 con `id_jugador` igual al pedido |

### CU05 — Ver la ficha de un partido (con caché)

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, al abrir un partido. Es la lectura más frecuente del sistema (≈ 20.000/s en el pico, según el Hito 7, PA3) |
| Recibe / envía | Recibe el código del partido. Envía fecha, fase, equipo local, equipo visitante y sede (código, nombre y ciudad) |
| Fuentes | **Neo4j** como fuente de verdad (`Partido`, `DISPUTA`, `SE_JUEGA_EN`, Hito 5) y **Redis** como caché (`cache:partido:<codigo>`, TTL 300 s, Hito 7) |
| Entrada necesaria | `codigo_partido` en la ruta |
| Validación previa | Formato `^P-\d{3}$` |
| Patrón de acceso | *Cache-aside*. (1) Hace `GET cache:partido:<codigo>` en Redis. (2) Si no está, ejecuta en Neo4j un Cypher parametrizado `MATCH (p:Partido {codigo_partido: $codigo}) OPTIONAL MATCH (e:Equipo)-[d:DISPUTA]->(p) OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)`. (3) Guarda el JSON con `SET ... EX 300` |
| Respuesta esperada | 200 con la ficha y el header `X-Cache: HIT` o `MISS` |
| Si el dato no existe | 404. La ausencia no se guarda en caché |
| Si la dependencia no está disponible | **Redis caído:** respuesta degradada documentada. Se consulta Neo4j directamente, se devuelve 200 con `X-Cache: BYPASS` y se registra una advertencia en el log. **Neo4j caído con caché vigente:** 200 desde la caché. **Neo4j caído sin caché:** 503 o 504 |
| Tipo de operación | Lectura. Escribe en la caché como efecto interno, sin efecto visible para el consumidor |
| Criterio de éxito | La ficha coincide con Neo4j. Una segunda lectura dentro de los 300 s devuelve `X-Cache: HIT` |
| Riesgo de frescura | Un cambio en Neo4j puede tardar hasta 300 s en verse. Se acepta porque la ficha cambia de 10 a 20 veces por partido (Hito 7, `ciclo_de_vida_e_invalidacion.md`) |

### CU06 — Ver los eventos de un partido

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en la línea de tiempo del partido |
| Recibe / envía | Recibe el partido. Envía la lista de eventos (`id_evento`, `tipo`, `minuto`) con el jugador que lo protagonizó (`id_jugador`, `nombre`) |
| Fuente | Neo4j: `(Evento)-[:CORRESPONDE_A]->(Partido)` y `(Jugador)-[:PROTAGONIZA]->(Evento)` |
| Entrada necesaria | `codigo_partido` en la ruta. Query opcional: `limit` |
| Validación previa | Formato del código. `limit` entre 1 y 200 (por defecto 50) |
| Patrón de acceso | Un único Cypher parametrizado: `MATCH (p:Partido {codigo_partido: $codigo}) OPTIONAL MATCH (ev:Evento)-[:CORRESPONDE_A]->(p) OPTIONAL MATCH (j:Jugador)-[:PROTAGONIZA]->(ev) RETURN p.codigo_partido, ev, j ORDER BY ev.minuto LIMIT $limit`. El recorrido parte siempre de un partido concreto y tiene profundidad 2 |
| Respuesta esperada | 200 con `{ "codigo_partido": "P-001", "eventos": [...] }` |
| Si el dato no existe | **Partido inexistente:** el `MATCH` no devuelve filas y la respuesta es 404. **Partido sin eventos:** el `MATCH` encuentra el partido pero el `OPTIONAL MATCH` no trae eventos, así que la respuesta es 200 con `eventos: []`. Así se diferencian los dos casos (sección 5.6) |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura limitada |
| Criterio de éxito | Los eventos vienen ordenados por minuto, son `limit` como máximo y pertenecen al partido pedido |

### CU07 — Ver los rivales de una selección

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en la sección "Próximos rivales" |
| Recibe / envía | Recibe la selección. Envía cada rival con el partido, la fecha y la condición (local o visitante) |
| Fuente | Neo4j: `(Equipo)-[:DISPUTA]->(Partido)<-[:DISPUTA]-(Equipo)` |
| Entrada necesaria | `codigo_iso`. Query opcional: `limit` |
| Validación previa | Formato ISO. `limit` entre 1 y 20 (por defecto 10) |
| Patrón de acceso | Consulta 1 de `consultas_grafo.cypher` (Hito 5), parametrizada con `$codigo_iso` y `LIMIT $limit` |
| Respuesta esperada | 200 con la lista de rivales |
| Si el dato no existe | Selección inexistente en el grafo: 404. Selección sin partidos cargados: 200 con `[]` |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura limitada |
| Criterio de éxito | Ningún rival es la propia selección y cada rival comparte un partido con ella |

### CU08 — Leer el muro de comentarios de un partido

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en el muro en vivo del partido |
| Recibe / envía | Recibe el partido, la ventana de un minuto y un cursor opcional. Envía comentarios del más reciente al más viejo (`id_comentario`, `usuario_alias`, `equipo_apoyado`, `texto`, `idioma`, `minuto_partido`, `creado_en`) y el `cursor_siguiente` |
| Fuente | Cassandra, keyspace `fixture2030`, tabla `comentarios_por_partido` (Hito 6, Q1) |
| Entrada necesaria | `codigo_partido` en la ruta. Query: `ventana` (obligatoria), `limit` y `cursor` (opcionales) |
| Validación previa | `ventana` con formato `AAAAMMDDHHMM` y fecha válida. `limit` entre 1 y 100 (por defecto 20). `cursor` debe ser un `timeuuid` válido |
| Patrón de acceso | La clave de partición es `(id_partido, ventana, shard)` con `shard` de 0 a 3. El adaptador ejecuta 4 lecturas, una por shard, cada una con la partición completa: `WHERE id_partido=? AND ventana=? AND shard=? [AND id_comentario < ?cursor] LIMIT ?`. Une los resultados ordenando por `id_comentario` descendente y corta en `limit`. El `cursor_siguiente` es el `id_comentario` del último elemento devuelto. **Nunca se usa `ALLOW FILTERING` ni un escaneo del partido completo** |
| Respuesta esperada | 200 con `{ "items": [...], "cursor_siguiente": "<timeuuid>" | null }` |
| Si el dato no existe | Ventana sin comentarios: 200 con `items: []`. **No se verifica que el partido exista** en otra fuente, para no agregar una lectura a Neo4j en la consulta más frecuente del muro. Esta decisión queda documentada en el contrato |
| Si la dependencia no está disponible | 503 o 504. Si falla una de las 4 lecturas, falla toda la respuesta: no se devuelve un muro parcial como si fuera completo |
| Tipo de operación | Lectura por partición con cursor (RNF12, RNF13) |
| Criterio de éxito | Hay como máximo `limit` comentarios, en orden descendente, todos del partido y la ventana pedidos. Repetir la consulta con `cursor` no repite elementos |

### CU09 — Publicar un comentario

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, cuando el usuario envía un comentario en el muro |
| Recibe / envía | Recibe `id_usuario`, `usuario_alias`, `equipo_apoyado`, `texto`, `idioma` y `minuto_partido`. Envía el comentario creado con `id_comentario`, `ventana`, `creado_en` y `estado_moderacion` |
| Fuentes | **Cassandra** para escribir. **Neo4j** para verificar que el partido existe. **Redis** para registrar la clave de idempotencia |
| Entrada necesaria | `codigo_partido` en la ruta, el cuerpo JSON y el header obligatorio `Idempotency-Key` (UUID) |
| Validación previa | `id_usuario` con formato `U-NNNN`. `usuario_alias` de 3 a 30 caracteres alfanuméricos, `_` o `.`. `texto` de 1 a 500 caracteres. `idioma` ∈ {es, pt, en}. `equipo_apoyado` con formato ISO. `minuto_partido` entre 0 y 130. `Idempotency-Key` con formato UUID. Se rechazan campos no definidos en el esquema (por ejemplo `estado_moderacion`). Un cuerpo inválido da 400 sin tocar ninguna base |
| Patrón de acceso | (1) Reserva la clave con `SET idem:comentario:<key> {huella, en_curso} NX EX 86400` en Redis. (2) Comprueba en Neo4j que el partido exista. (3) Calcula `ventana` (minuto actual en UTC), `shard = crc32(id_usuario) % 4`, `periodo` (AAAAMM) e `id_comentario` (timeuuid). (4) Hace un `BATCH` logged sobre `comentarios_por_partido` y `comentarios_por_usuario`, igual que la duplicación controlada del Hito 6. (5) Guarda en la clave de idempotencia la respuesta completa (`SET XX KEEPTTL`) |
| Respuesta esperada | 201 con el comentario y el header `Location` |
| Si el dato no existe | Partido inexistente: 404 |
| Si la dependencia no está disponible | Cualquiera de las tres fuentes caída: 503 o 504. Sin Redis no se garantiza la idempotencia, así que no se escribe |
| Tipo de operación | **Creación** |
| Idempotencia (RF19, RNF14) | Un reintento con la misma `Idempotency-Key` y el mismo cuerpo devuelve 200 con el **mismo** `id_comentario` y el header `Idempotent-Replayed: true`, sin volver a escribir. La misma clave con un cuerpo distinto, o mientras la primera request todavía está en curso, da 409 `CONFLICTO_IDEMPOTENCIA`. Una clave nueva siempre crea un comentario nuevo: dos envíos distintos del mismo texto se consideran dos comentarios. Si la escritura falla (404, 503, 504) la clave se libera para que el cliente pueda reintentar |
| Criterio de éxito | 201, y el comentario aparece en CU08 para la ventana indicada |

### CU10 — Validar una sesión

| Aspecto | Definición |
|---|---|
| Consumidor | Gestor de sesiones de la app, en cada petición de un usuario logueado (Hito 7, PA1) |
| Recibe / envía | Recibe `id_sesion`. Envía `id_sesion`, `usuario_id`, `rol`, `estado` y `ttl_restante_s`. **No envía** `dispositivo`, `paginas_vistas`, `creada_en` ni `ultimo_acceso` |
| Fuente | Redis, hash `sesion:<id_sesion>` |
| Entrada necesaria | `id_sesion` en la ruta |
| Validación previa | Formato `^S-\d{4,}$` |
| Patrón de acceso | `HMGET sesion:<id> usuario_id rol estado` y `TTL sesion:<id>` en un pipeline. **El GET no renueva el TTL**: la lectura no tiene efectos. La renovación por actividad queda fuera del alcance de esta API |
| Respuesta esperada | 200 con los cuatro campos |
| Si el dato no existe | Clave inexistente o expirada: 404 `SESION_NO_VIGENTE`. Redis no distingue "nunca existió" de "expiró", porque al expirar borra la clave, así que la API responde lo mismo en los dos casos |
| Si la dependencia no está disponible | **503** (conexión rechazada) o **504** (timeout). Una clave inexistente se recibe como una respuesta válida de Redis (`nil` y `TTL -2`), mientras que Redis caído es una excepción del cliente. Así se distinguen los dos casos (sección 5.8). Con Docker Desktop, un contenedor detenido suele verse como timeout (504): el puerto publicado sigue aceptando la conexión TCP pero no responde |
| Tipo de operación | Lectura |
| Criterio de éxito | 200 con `ttl_restante_s` > 0 para una sesión vigente, y 404 una vez vencido el TTL |

### CU11 — Cerrar una sesión

| Aspecto | Definición |
|---|---|
| Consumidor | Gestor de sesiones (logout) o un administrador que suspende a un usuario (Hito 7, PA2) |
| Recibe / envía | Recibe `id_sesion`. No envía cuerpo |
| Fuente | Redis |
| Entrada necesaria | `id_sesion` en la ruta |
| Validación previa | Formato `^S-\d{4,}$` |
| Patrón de acceso | `DEL sesion:<id>` |
| Respuesta esperada | 204 |
| Si el dato no existe | 204. El resultado buscado, "la sesión ya no es válida", se cumple igual |
| Si la dependencia no está disponible | 503 o 504. Nunca se responde 204 si el `DEL` no se ejecutó |
| Tipo de operación | **Invalidación** |
| Idempotencia | Idempotente: repetir el `DELETE` deja siempre el mismo estado y devuelve 204 |
| Criterio de éxito | Un `GET /sesiones/{id}` posterior devuelve 404 |

### CU12 — Ver estadísticas en vivo de un partido

| Aspecto | Definición |
|---|---|
| Consumidor | App del hincha, en la pantalla de estadísticas en vivo (Hito 8, patrón 1) |
| Recibe / envía | Recibe el partido, la ventana de tiempo, la resolución y opcionalmente el equipo. Envía, para cada equipo, la serie de puntos `{ instante, posesion_pct_prom, pases_completados_max, tiros_max, usuarios_activos_max }` y la resolución aplicada |
| Fuente | InfluxDB 3, database `fixture2030`, tabla `estadisticas_partido` |
| Entrada necesaria | `codigo_partido` en la ruta. Query: `desde` y `hasta` (obligatorios), `resolucion` (por defecto `1m`) y `equipo` (opcional) |
| Validación previa | `desde` y `hasta` en ISO 8601 UTC. `desde < hasta`. La ventana dura **3 horas como máximo**. `resolucion` ∈ {`10s`, `1m`, `5m`}. `equipo` con formato ISO. Cualquier violación da 400 sin consultar |
| Patrón de acceso | SQL parametrizado (`/api/v3/query_sql` con `params`) que filtra por los tags `partido_id` (y `equipo_id` si se indica) y por `time` en `[desde, hasta)`, agrupado con `date_bin(resolucion, time)`. Usa las agregaciones correctas del Hito 8: `AVG` para la posesión y `MAX` para los contadores acumulados y la audiencia. El intervalo de `date_bin` sale de una lista cerrada, no del consumidor. El tope de puntos es 3 h / 10 s + 1 = 1.081 por equipo, 2.162 por respuesta, y se aplica también como `LIMIT` en la consulta (RNF12) |
| Respuesta esperada | 200 con `{ "codigo_partido", "desde", "hasta", "resolucion", "series": [ { "equipo", "puntos": [...] } ] }` |
| Si el dato no existe | Una ventana sin puntos da 200 con `series: []`. En una serie temporal, la ausencia de puntos es un resultado válido (Hito 8, patrón 4) y no se inventan valores |
| Si la dependencia no está disponible | 503 o 504, nunca `series: []` |
| Tipo de operación | Lectura por ventana temporal |
| Criterio de éxito | Todos los instantes caen dentro de `[desde, hasta)`, están alineados a la resolución y la cantidad de puntos no supera el tope |

### CU13 — Ver el acta oficial de un partido

| Aspecto | Definición |
|---|---|
| Consumidor | Mesa de control y app del hincha (resultado oficial) |
| Recibe / envía | Recibe el código del partido. Envía `codigo_partido`, `sede`, `fecha`, `estado`, el árbitro (`nombre`, `apellido`, `rango`) y los eventos (`minuto`, `tipo`, `descripcion`) ordenados por minuto |
| Fuente | InterSystems IRIS, namespace configurado, clases `Fixture.Partido`, `Fixture.Arbitro` y `Fixture.Evento` (Hito 9) |
| Entrada necesaria | `codigo_partido` en la ruta |
| Validación previa | Formato `^P-\d{3}$` |
| Patrón de acceso | La API invoca por la Native API el método `Fixture.API.ObtenerActa` (`iris/Fixture.API.cls`), que abre `Fixture.Partido` por su índice único `Codigo` y recorre la relación `Eventos` y la referencia `Arbitro`. El `%ID` interno de IRIS y el `DNI` del árbitro **no** se publican |
| Respuesta esperada | 200 con el acta |
| Si el dato no existe | 404 |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | Lectura |
| Criterio de éxito | El acta incluye el árbitro y todos los eventos asociados al partido |

### CU14 — Cambiar el estado de un partido oficial

| Aspecto | Definición |
|---|---|
| Consumidor | Mesa de control, al dar inicio y al cerrar el partido |
| Recibe / envía | Recibe `{ "estado": "En Juego" }`. Envía el acta con el estado nuevo |
| Fuente | IRIS, `Fixture.Partido` |
| Entrada necesaria | `codigo_partido` en la ruta y `estado` en el cuerpo |
| Validación previa | `estado` ∈ {Programado, En Juego, Finalizado} (el `VALUELIST` del Hito 9). Un valor desconocido da 400 sin abrir el objeto |
| Patrón de acceso | `Fixture.API.CambiarEstado` abre el partido con bloqueo exclusivo, valida la transición con la máquina de estados **Programado → En Juego → Finalizado** y solo si es válida ejecuta `%Save()` |
| Respuesta esperada | 200 con el acta actualizada |
| Si el dato no existe | 404 |
| Conflicto de negocio | Una transición no permitida (Finalizado → En Juego, Programado → Finalizado, etc.) da 409 `CONFLICTO_ESTADO` con el estado actual en `detalles`. No se persiste ningún cambio |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | **Actualización** |
| Idempotencia | Pedir el estado en el que el partido ya está devuelve 200 sin modificarlo. Por eso reintentar la misma transición es seguro |
| Criterio de éxito | Un CU13 posterior muestra el estado nuevo. Las transiciones inválidas nunca quedan persistidas |

### CU15 — Registrar un evento en el acta

| Aspecto | Definición |
|---|---|
| Consumidor | Mesa de control, durante el partido |
| Recibe / envía | Recibe `{ "minuto", "tipo", "descripcion" }`. Envía el evento creado con su posición en el acta |
| Fuentes | **IRIS** para persistir. **Redis** para la clave de idempotencia, con el mismo mecanismo que CU09 |
| Entrada necesaria | `codigo_partido` en la ruta, el cuerpo JSON y el header obligatorio `Idempotency-Key` |
| Validación previa | `minuto` entero entre 1 y 130. `tipo` ∈ {Gol, Tarjeta Amarilla, Tarjeta Roja, Cambio}. `descripcion` de 200 caracteres como máximo. Se validan en la API **antes** de llegar a IRIS, que vuelve a validarlas con `MINVAL`, `MAXVAL` y `VALUELIST` como segunda barrera |
| Patrón de acceso | `Fixture.API.RegistrarEvento` abre el partido, crea el `Fixture.Evento`, lo asocia a la relación y ejecuta `%Save()`. La regla `%OnBeforeSave()` del Hito 9 rechaza el guardado si el partido está Finalizado |
| Respuesta esperada | 201 |
| Si el dato no existe | Partido inexistente: 404 |
| Conflicto de negocio | Partido en estado Finalizado: 409 `CONFLICTO_ESTADO`. El adaptador traduce el `%Status` de error de `%OnBeforeSave` a una excepción de dominio, sin exponer el mensaje interno de IRIS |
| Si la dependencia no está disponible | 503 o 504 |
| Tipo de operación | **Creación** |
| Idempotencia | Igual que CU09. Un reintento con la misma clave devuelve el evento ya creado, sin duplicar un gol en el acta |
| Criterio de éxito | El evento aparece en CU13. Intentar registrarlo con el partido Finalizado nunca lo persiste |

### CU16 — Verificar la disponibilidad de las fuentes

| Aspecto | Definición |
|---|---|
| Consumidor | Equipo de operación y el script `verificar_conectividad` |
| Recibe / envía | No recibe parámetros. Envía, por cada fuente, `estado` (`ok`, `caida` o `timeout`) y la latencia del chequeo en ms |
| Fuentes | Las seis: MongoDB (`ping`), Neo4j (`RETURN 1`), Cassandra (`SELECT release_version FROM system.local`), Redis (`PING`), InfluxDB (`SELECT 1`) e IRIS (`%SYSTEM.Version.GetNumber()` por la Native API) |
| Entrada necesaria | Ninguna |
| Validación previa | No aplica |
| Patrón de acceso | Una operación trivial por fuente, en paralelo y con el timeout de cada adaptador. No lee datos de negocio |
| Respuesta esperada | 200 si las seis responden. **503** si al menos una falla, con el detalle de cuál falló. Nunca un 200 con una dependencia caída |
| Si el dato no existe | No aplica |
| Si la dependencia no está disponible | Se informa en el cuerpo con el estado `caida` o `timeout`. Nunca se exponen el host, el puerto ni el mensaje del driver |
| Tipo de operación | Lectura |
| Criterio de éxito | Con todos los contenedores levantados, 200. Al detener uno, 503 que señala exactamente esa fuente |

---

## 5. Resumen de lectura, escritura e idempotencia (RF19)

| CU | Operación | ¿Produce cambios? | Comportamiento ante repetición |
|---|---|---|---|
| CU01–CU08, CU10, CU12, CU13, CU16 | Lectura | No (CU05 solo escribe en la caché interna) | Seguro: repetir no tiene efecto |
| CU09 | Creación | Sí, en Cassandra | `Idempotency-Key` obligatoria. La misma clave no duplica |
| CU11 | Invalidación | Sí, en Redis | Idempotente por naturaleza (`DEL`) |
| CU14 | Actualización | Sí, en IRIS | Idempotente: el mismo estado destino no cambia nada |
| CU15 | Creación | Sí, en IRIS | `Idempotency-Key` obligatoria. La misma clave no duplica |

## 6. Cobertura de la especificación técnica

| Sección del enunciado | Casos que la cubren |
|---|---|
| 5.5 MongoDB: driver, database, paginación, proyección, ausencia | CU01–CU04 |
| 5.6 Neo4j: Cypher parametrizado, límites, partido inexistente vs. sin eventos | CU05–CU07 |
| 5.7 Cassandra: keyspace, partición, cursor, escritura repetida | CU08, CU09 |
| 5.8 Redis: TTL, clave inexistente vs. Redis caído, invalidación | CU05, CU10, CU11 |
| 5.9 InfluxDB: intervalo, orden de límites, sin puntos vs. caída, tope de puntos | CU12 |
| 5.10 IRIS: namespace, identificadores, transición validada, conflicto | CU13–CU15 |
| 5.11 Validación, ausencia, sesión expirada, conflicto, dependencia, error interno | Sección 3 y todas las fichas |
| 5.12 Respuesta vacía válida | CU02, CU03, CU06, CU08, CU12 |
| RNF12 Paginación y límites | CU02, CU03, CU06, CU07, CU08, CU12 |
| RNF14 Idempotencia | Sección 5 |

## 7. Ajustes realizados en los módulos anteriores

Para que todas las fuentes usen los mismos identificadores se hicieron estos
ajustes, sin borrar ni reemplazar los datos de los hitos anteriores:

1. **InfluxDB (CU12).** El generador del Hito 8 usa `partido_id = M001` y
   `equipo_id = EQ001_1`. En lugar de regenerar ese volumen, el script
   `scripts/datos/cargar_estadisticas_influx.py` escribe en la misma tabla y
   con el mismo modelo los partidos `P-001` (ARG–ESP) y `P-002` (URU–ARG), con
   un punto por segundo durante 2 horas. Suma 4 series a la cardinalidad
   (2 por partido, como en el Hito 8) y es idempotente.
2. **IRIS (CU13–CU15).** `Fixture.Partido` tiene ahora la propiedad `Codigo`
   (opcional, para no invalidar las actas creadas por la demo del Hito 9) con
   el índice único `CodigoIndex`. La fachada `Fixture.API`
   (`iris/Fixture.API.cls`) concentra las operaciones que usa la API y el
   método `CargarMuestra()`, que reinicia las actas `P-001` (En Juego),
   `P-002` (Programado) y `P-003` (Finalizado).
3. **Datos de muestra.** `scripts/preparar_datos.sh` deja las seis fuentes
   con los mismos códigos: `P-001` y `P-002` existen en Neo4j, Redis,
   InfluxDB e IRIS. `P-003` existe solo en Cassandra (muestra del Hito 6) y en
   IRIS: por eso `POST /partidos/P-003/comentarios` responde 404 (el fixture
   de Neo4j no lo tiene) mientras que su acta se puede consultar.

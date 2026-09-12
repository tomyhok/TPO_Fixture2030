# Modelo Tabular — Módulo de Comentarios Masivos (Cassandra)

Referencia columna por columna del esquema definido en
`scripts/02-tablas.cql`. La justificación de cada decisión está en
[`analisis_hito6.md`](analisis_hito6.md).

## Keyspace

| Propiedad | Valor | Nota |
|---|---|---|
| Nombre | `fixture2030` | Mismo nombre lógico que la base del Hito 4 |
| Estrategia | `SimpleStrategy` | Laboratorio de un solo nodo |
| Factor de replicación | `1` | En producción: `NetworkTopologyStrategy`, RF=3 por DC |
| `durable_writes` | `true` | Commit log activo |

## Convenciones de clave

| Campo derivado | Formato | Cómo se calcula | Quién lo calcula |
|---|---|---|---|
| `ventana` | `AAAAMMDDHHMM` | Instante del comentario truncado al minuto | El productor |
| `shard` | `0..3` | `crc32(id_usuario) % 4` | El productor |
| `periodo` | `AAAAMM` | Instante del comentario truncado al mes | El productor |
| `id_comentario` | `timeuuid` | `now()` en producción; valores fijos en la muestra | El productor |

---

## Tabla 1 — `comentarios_por_partido`

**Consulta que la motiva:** Q1 / Q1b — muro en vivo de un partido, del
comentario más reciente al más viejo.

**Clave primaria:** `((id_partido, ventana, shard), id_comentario)`
**Orden de clustering:** `id_comentario DESC`

| Columna | Tipo | Rol | Descripción |
|---|---|---|---|
| `id_partido` | `text` | Partición | `P-001` … `P-064`; mismo id que el nodo `:Partido` de Neo4j |
| `ventana` | `text` | Partición | Bucket temporal de 1 minuto |
| `shard` | `int` | Partición | Sub-partición anti-hotspot, `0..3` |
| `id_comentario` | `timeuuid` | Clustering (DESC) | Identidad + instante de creación |
| `id_usuario` | `text` | Dato | Autor; referencia lógica al usuario |
| `usuario_alias` | `text` | Dato | Alias desnormalizado para renderizar sin segunda lectura |
| `equipo_apoyado` | `text` | Dato | `codigo_iso` del equipo (Hito 4) |
| `texto` | `text` | Dato | Contenido del comentario |
| `idioma` | `text` | Dato (indexado) | `es` \| `pt` \| `en` |
| `estado_moderacion` | `text` | Dato | `publicado` \| `en_revision` \| `rechazado` |
| `minuto_partido` | `int` | Dato | Contexto deportivo: minuto de juego |
| `creado_en` | `timestamp` | Dato | Legible; redundante con el `timeuuid` |

**Opciones de tabla**

| Opción | Valor | Motivo |
|---|---|---|
| `compaction` | TWCS, ventanas de 1 hora | Serie temporal de escritura intensiva |
| `caching` | `{keys: ALL, rows_per_partition: NONE}` | Las filas se leen una vez, en vivo; no conviene ocupar RAM |
| `default_time_to_live` | `0` | Registro histórico del torneo, sin expiración |

---

## Tabla 2 — `comentarios_por_usuario`

**Consulta que la motiva:** Q2 — historial mensual de un usuario.
**Naturaleza:** duplicación controlada de la tabla 1 (RF10).

**Clave primaria:** `((id_usuario, periodo), id_comentario)` — clustering `DESC`

| Columna | Tipo | Rol |
|---|---|---|
| `id_usuario` | `text` | Partición |
| `periodo` | `text` | Partición (`AAAAMM`) |
| `id_comentario` | `timeuuid` | Clustering (DESC) |
| `id_partido` | `text` | Dato |
| `texto` | `text` | Dato |
| `estado_moderacion` | `text` | Dato |
| `creado_en` | `timestamp` | Dato |

No replica `equipo_apoyado`, `idioma` ni `minuto_partido`: el historial de perfil
no los muestra, y cada columna omitida se ahorra 96 M de veces.

---

## Tabla 3 — `comentarios_en_revision`

**Consulta que la motiva:** Q3 — cola FIFO de moderación por partido.
**Regla de escritura:** solo se insertan filas con `estado_moderacion ≠ publicado`.

**Clave primaria:** `((id_partido, estado_moderacion), id_comentario)` — clustering `ASC`

| Columna | Tipo | Rol |
|---|---|---|
| `id_partido` | `text` | Partición |
| `estado_moderacion` | `text` | Partición (`en_revision` \| `rechazado`) |
| `id_comentario` | `timeuuid` | Clustering (ASC — orden de llegada) |
| `id_usuario` | `text` | Dato |
| `texto` | `text` | Dato |
| `motivo` | `text` | Dato (`reporte_usuario` \| `filtro_automatico`) |
| `creado_en` | `timestamp` | Dato |

| Opción | Valor | Motivo |
|---|---|---|
| `default_time_to_live` | `604800` (7 días) | Red de seguridad contra una cola desatendida |
| `gc_grace_seconds` | `86400` (1 día) | Nodo único: los tombstones se recolectan rápido sin riesgo de resurrección |

---

## Tabla 4 — `metricas_comentario`

**Consulta que la motiva:** Q4 — likes, reportes y respuestas de un comentario.

**Clave primaria:** `(id_comentario)`

| Columna | Tipo | Rol |
|---|---|---|
| `id_comentario` | `timeuuid` | Partición |
| `likes` | `counter` | Dato |
| `reportes` | `counter` | Dato |
| `respuestas` | `counter` | Dato |

Restricciones propias de los `counter`, asumidas en el diseño:

- Solo admiten `UPDATE ... SET c = c + n`, nunca `INSERT`.
- No son idempotentes: reejecutar un incremento vuelve a sumar.
- Una clave borrada no debe reutilizarse. No es un riesgo aquí porque
  `id_comentario` es un `timeuuid` irrepetible.

---

## Índice secundario — `idx_idioma_comentario`

`CREATE INDEX idx_idioma_comentario ON comentarios_por_partido (idioma);`

Creado con fines comparativos (RF10). Uso aceptable únicamente combinado con la
clave de partición completa. Sin ella, la consulta degenera en *scatter-gather*
sobre todo el anillo. La medición de ambos casos está en
`scripts/06-medicion.cql`, punto 4.

---

## Mapa consulta → tabla

| Consulta | Tabla | Particiones tocadas |
|---|---|---|
| Q1 — muro en vivo | `comentarios_por_partido` | 4 (una por shard), en paralelo |
| Q1b — scroll dentro de la ventana | `comentarios_por_partido` | 1 por shard |
| Q2 — historial de usuario | `comentarios_por_usuario` | 1 |
| Q3 — cola de moderación | `comentarios_en_revision` | 1 |
| Q4 — métricas | `metricas_comentario` | 1 (o N con `IN`) |
| Moderación por idioma | `comentarios_por_partido` + índice | 1 (con clave de partición) |

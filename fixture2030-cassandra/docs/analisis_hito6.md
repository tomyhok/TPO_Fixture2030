# Hito 6 — Análisis Técnico del Módulo de Comentarios Masivos (Apache Cassandra)

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los ocho apartados exigidos por la sección 8 del enunciado.
El detalle columna por columna del esquema está en [`modelo_tabular.md`](modelo_tabular.md)
y los resultados de ejecución en [`evidencia.md`](evidencia.md).

---

## 1. Problema de volumen

El módulo de comentarios es el único componente del Fixture 2030 donde la
escritura domina sobre la lectura estructurada y donde el volumen no depende de
la cantidad de entidades deportivas, sino de la cantidad de hinchas conectados.

**Supuestos de carga declarados** (base de todas las decisiones posteriores):

| Supuesto | Valor asumido | Origen |
|---|---|---|
| Partidos del torneo | 64 | Fixture definido en el Hito 1 |
| Partidos simultáneos (fase de grupos) | hasta 4 | Calendario del Hito 1 |
| Duración de la ventana de escritura por partido | 120 minutos | Partido + entretiempo + previa/post |
| Tasa media de comentarios, partido común | 300 escrituras/s | Estimación del equipo |
| Tasa media, partido popular (ARG–BRA, final) | 800 escrituras/s | Estimación del equipo |
| Pico instantáneo, partido popular (gol, penal, expulsión) | 3.000 escrituras/s | Estimación del equipo |
| Comentarios totales de un partido popular | ≈ 5.800.000 | 800/s × 7.200 s |
| Comentarios totales del torneo | ≈ 96.000.000 | 64 partidos × 1,5 M promedio |
| Lectores concurrentes del muro, partido popular | 50.000 | Estimación del equipo |
| Frecuencia de refresco del muro por lector | cada 10 s | Definición de producto |
| Lecturas del muro por segundo, partido popular | ≈ 5.000 | 50.000 / 10 s |
| Tamaño medio de una fila de comentario | ≈ 350 bytes | Texto ~140 B + claves + overhead |

La relación lectura/escritura es de aproximadamente **6 lecturas por cada
escritura**, pero ambas son de acceso conocido y acotado: nadie consulta
"todos los comentarios del torneo". Ese es exactamente el escenario para el que
sirve un modelo tabular de columnas anchas, y la razón por la que este módulo no
se resuelve con el modelo documental del Hito 4 ni con el grafo del Hito 5.

---

## 2. Patrones de acceso

Las consultas se definieron **antes** que las tablas (RF3). Solo estas cinco
preguntas se consideran prioritarias:

| ID | Pregunta | Parámetros de entrada | Orden | Límite | Frecuencia estimada |
|---|---|---|---|---|---|
| **Q1** | ¿Cuáles son los últimos comentarios publicados de este partido? | `id_partido`, ventana de 1 min, `shard` | `id_comentario` DESC | 20 por shard | ~5.000/s en partido popular |
| **Q1b** | ¿Qué se comentó justo antes de lo que ya estoy viendo? (scroll) | Q1 + cota `id_comentario <` | `id_comentario` DESC | 10–20 | ~500/s |
| **Q2** | ¿Qué comentó este usuario durante el mes? | `id_usuario`, `periodo` | `id_comentario` DESC | 20 | ~50/s |
| **Q3** | ¿Qué comentarios de este partido esperan moderación? | `id_partido`, `estado_moderacion` | `id_comentario` ASC (FIFO) | 50 | ~5/s |
| **Q4** | ¿Cuántos likes y reportes tiene este comentario? | `id_comentario` | — | 1 fila | ~2.000/s |

Todo lo que no está en esta tabla (rankings globales, búsqueda por texto libre,
reportes analíticos históricos) queda **fuera del módulo**: se resuelve con un
proceso batch sobre un almacén analítico, no agregando tablas a Cassandra.
Ver el apartado 8.

---

## 3. Modelo propuesto

**Keyspace:** `fixture2030`, `SimpleStrategy` con `replication_factor = 1`
(nodo único de laboratorio; ver apartado 4 para la diferencia con producción).

| Tabla | Consulta que la justifica | Clave de partición | Clustering |
|---|---|---|---|
| `comentarios_por_partido` | Q1, Q1b | `(id_partido, ventana, shard)` | `id_comentario` DESC |
| `comentarios_por_usuario` | Q2 | `(id_usuario, periodo)` | `id_comentario` DESC |
| `comentarios_en_revision` | Q3 | `(id_partido, estado_moderacion)` | `id_comentario` ASC |
| `metricas_comentario` | Q4 | `(id_comentario)` | — (counters) |
| `idx_idioma_comentario` | comparativa de RF10 | índice secundario local sobre `idioma` | — |

Ninguna tabla existe sin una consulta asociada (RNF4). El esquema completo, con
tipos de dato y opciones de compactación, está en `scripts/02-tablas.cql` y
descrito en [`modelo_tabular.md`](modelo_tabular.md).

**Convenciones de particionado**

- `ventana`: texto `AAAAMMDDHHMM`, bucket temporal de **1 minuto**.
- `shard`: entero `0..3`, calculado por el productor como `crc32(id_usuario) % 4`.
- `periodo`: texto `AAAAMM`, bucket mensual del historial de usuario.

---

## 4. Decisiones de diseño

### 4.1 Tabla de decisiones

| Decisión | Alternativas consideradas | Elección | Justificación técnica | Impacto esperado |
|---|---|---|---|---|
| **Clave de partición del muro** | 1. `id_partido` solo.<br>2. `(id_partido, ventana)`.<br>3. `(id_partido, ventana, shard)`. | **`(id_partido, ventana, shard)`** | Con solo `id_partido`, un partido popular acumula ~5.800.000 filas (≈2 GB) en una única partición: inviable. Agregando la ventana de 1 minuto la partición baja a ~180.000 filas en el pico, todavía por encima del umbral práctico de ~100.000 filas. El `shard` derivado del autor divide ese pico en 4 particiones de ~45.000 filas (~15 MB). | Particiones acotadas y predecibles; la escritura del pico se reparte entre 4 réplicas lógicas distintas en lugar de concentrarse en una. |
| **Clustering del muro** | 1. `creado_en` + `id_comentario`.<br>2. `id_comentario timeuuid`. | **`id_comentario timeuuid DESC`** | El timeuuid ya lleva el instante embebido y además desempata por unicidad, así que una sola columna de clustering resuelve orden y unicidad. `DESC` hace que el muro en vivo lea el prefijo físico de la partición, sin recorrerla. Las funciones `minTimeuuid`/`maxTimeuuid` permiten igual consultar por rango de tiempo. | Una columna menos por fila en ~96 M de filas, y lecturas de los últimos N comentarios en tiempo constante. |
| **Duplicación para el historial** | 1. Índice secundario por `id_usuario` sobre la tabla principal.<br>2. Tabla `comentarios_por_usuario` duplicada. | **Tabla duplicada** | Un índice local por `id_usuario` obliga al coordinador a consultar todos los nodos con datos (*scatter-gather*): el tiempo de respuesta crece con el tamaño del cluster. La tabla duplicada resuelve Q2 tocando una sola partición. | Costo: una escritura extra por comentario (2× write amplification) y coherencia a cargo de la aplicación. Beneficio: Q2 con latencia constante y predecible. |
| **Cola de moderación** | 1. Filtrar `estado_moderacion` con `ALLOW FILTERING`.<br>2. Índice secundario sobre `estado_moderacion`.<br>3. Tabla `comentarios_en_revision`. | **Tabla dedicada, solo con estados ≠ `publicado`** | `ALLOW FILTERING` escanea el anillo entero. El índice sobre `estado_moderacion` tiene cardinalidad muy baja (3 valores): el 92 % de las filas caería en la misma entrada de índice, que es el peor caso posible. La tabla dedicada guarda solo el 8 % de los comentarios y mantiene la partición chica. | Q3 resuelta en una partición; el volumen de la cola crece con los reportes, no con el tráfico total. |
| **Métricas de interacción** | 1. Columnas `int` en la tabla principal actualizadas con `UPDATE`.<br>2. Columnas `counter` en tabla separada. | **Tabla `metricas_comentario` con `counter`** | Un like es un incremento concurrente: con `int` se pierden actualizaciones (*lost update*) salvo usando LWT, que cuesta ~4 viajes de red por operación. Además Cassandra prohíbe mezclar `counter` con columnas normales en la misma tabla. | Contadores correctos bajo concurrencia sin Paxos. Costo aceptado: los counters no son idempotentes ni se pueden re-incrementar tras un borrado. |
| **Estrategia de compactación** | 1. `SizeTieredCompactionStrategy` (default).<br>2. `TimeWindowCompactionStrategy`. | **TWCS con ventanas de 1 hora** | Los comentarios son una serie temporal de escritura intensiva que se lee casi solo mientras es reciente. TWCS agrupa cada hora en sus propias SSTables, evita reescribir datos viejos y permite descartar SSTables completas cuando el dato expira. | Menos amplificación de escritura durante los partidos y compactaciones más baratas. |
| **Replicación del laboratorio** | 1. `SimpleStrategy` RF=1.<br>2. `NetworkTopologyStrategy` RF=3. | **`SimpleStrategy` RF=1** | Con un solo nodo no hay dónde ubicar réplicas adicionales: cualquier RF>1 deja las escrituras con `QUORUM` en estado `UNAVAILABLE`. | Ambiente reproducible en una notebook. **No es una topología de alta disponibilidad** y no debe presentarse como tal. |

### 4.2 Riesgo de hotspot y cómo se mitiga (RNF5, preguntas guía 2 y 6)

Sin `shard`, todas las escrituras de un mismo minuto de un partido popular caen
en un solo token del anillo. En un cluster real eso significa que 3 nodos (los
que tienen esa réplica) absorben el 100 % del pico mientras el resto queda
ocioso: el cluster se satura al ~5 % de su capacidad teórica.

Con `shard = crc32(id_usuario) % 4`:

- El pico de 3.000 escrituras/s se reparte en 4 particiones de ~750/s.
- Las 4 particiones tienen tokens independientes y caen, con alta probabilidad,
  en conjuntos de réplicas distintos.
- El hash es del **autor**, no aleatorio: el mismo usuario siempre escribe en el
  mismo shard, lo que hace la escritura reproducible y depurable.

**Trade-off aceptado:** Q1 pasa de leer 1 partición a leer 4 y ordenar el
resultado en el cliente (*k-way merge* de 4 listas ya ordenadas, O(n log 4)).
Se prefirió esto a tener una partición caliente, porque 4 lecturas chicas en
paralelo son más baratas que una lectura de una partición de 2 GB.

**Elección del número de shards:** 4 es el mínimo que deja la partición pico por
debajo de 100.000 filas con los supuestos declarados. Subirlo a 8 o 16 bajaría
más el tamaño de partición pero duplicaría o cuadruplicaría el costo de Q1, que
es la consulta más frecuente del sistema. Si en producción la tasa real supera
los supuestos, el parámetro se sube **solo para los partidos marcados como
populares**, manteniendo 1 shard para el resto.

### 4.3 Límites declarados por partición

| Métrica | Partido común | Partido popular (pico) | Umbral de alerta |
|---|---|---|---|
| Filas por partición (ventana de 1 min) | ~4.500 | ~45.000 | 100.000 |
| Bytes por partición | ~1,6 MB | ~15,7 MB | 100 MB |
| Escrituras/s por partición | ~75 | ~750 | 3.000 |

Si la medición real (`nodetool tablestats`) muestra particiones cerca del
umbral, la reacción es reducir la ventana a 30 segundos antes que agregar
shards, porque acortar la ventana no encarece Q1.

### 4.4 TTL, borrado y tombstones (pregunta guía 7)

Cassandra materializa tanto `DELETE` como el vencimiento de un TTL como
*tombstones*, que sobreviven `gc_grace_seconds` y se leen junto con los datos
vivos hasta que la compactación los elimina. Por eso el módulo los usa con
criterio explícito:

| Dato | Política | Motivo |
|---|---|---|
| `comentarios_por_partido` | **Sin TTL** (`default_time_to_live = 0`) | Es el registro histórico del torneo. Aplicar TTL masivo a 96 M de filas generaría una avalancha de tombstones en lecturas de rango. La purga, si se decide, se hace por `TRUNCATE`/drop de tablas viejas, no por TTL. |
| `comentarios_por_usuario` | Sin TTL | Mismo criterio; su partición ya está acotada por `periodo`. |
| `comentarios_en_revision` | **TTL de 7 días** + `DELETE` al resolver el caso | La cola es de bajo volumen (~8 % de los comentarios) y efímera por definición. El TTL es la red de seguridad para que una cola desatendida no crezca sin límite. Con `gc_grace_seconds = 86400` (1 día en lugar de 10) los tombstones se recolectan rápido, lo que es correcto aquí porque el laboratorio tiene un solo nodo y no depende de *hinted handoff* prolongado. |
| `metricas_comentario` | Sin TTL, borrado explícito junto con el comentario | Un counter borrado no debe reutilizarse; el `id_comentario` es un timeuuid irrepetible, así que no hay riesgo. |

### 4.5 Estructura secundaria y su trade-off (RF10, pregunta guía 8)

Se implementaron **dos** soluciones de acceso secundario, con propósitos distintos:

1. **`comentarios_por_usuario` (duplicación controlada)** — la solución adoptada
   para Q2. Justificada arriba.
2. **`idx_idioma_comentario` (índice secundario local sobre `idioma`)** — creado
   para *demostrar y medir* el trade-off, no como solución recomendada. La
   consulta relevante es "comentarios en portugués de esta ventana del partido",
   usada por el equipo de moderación regional. Combinado con la clave de
   partición (caso 5a de `05-consultas.cql`) el índice filtra dentro de una sola
   partición y es aceptable. Sin clave de partición (caso 5b) degenera en
   scatter-gather. La diferencia se mide con `TRACING ON` en
   `scripts/06-medicion.cql`, punto 4.

---

## 5. Datos cargados

**Muestra de desarrollo** (`scripts/03-carga-muestra.cql`): 35 comentarios,
3 partidos, 12 usuarios, con `timeuuid` fijos en el script para que la carga sea
idempotente (RNF7). Alcanza para validar las cinco consultas y el CRUD completo.

**Volumen objetivo** (`tools/generar_comentarios.py` + `tools/carga_masiva.sh`):
generación sintética reproducible de **1.000.000 de comentarios** (2.000.000 de
filas contando la vista duplicada, más ~80.000 en la cola de moderación),
cargados con el comando `COPY` de `cqlsh` desde CSV.

Distribución declarada del dataset sintético:

| Dimensión | Distribución |
|---|---|
| Partidos | 64; el 20 % de los partidos concentra el 60 % de los comentarios (simula el partido popular) |
| Usuarios | 200.000 alias; los 5.000 más activos generan ~30 % del tráfico |
| Instantes | 120 ventanas de 1 minuto por partido, con picos gaussianos alrededor de los minutos 23, 44, 67 y 88 |
| Estados | 92 % `publicado`, 6 % `en_revision`, 2 % `rechazado` |
| Idiomas | 55 % `es`, 25 % `pt`, 20 % `en` |
| Shards | `crc32(id_usuario) % 4` — distribución verificada en `06-medicion.cql`, punto 3 |

La semilla del generador es fija (`--semilla 2030`), de modo que dos integrantes
distintos producen exactamente el mismo dataset.

---

## 6. Operaciones CQL

| Script | Propósito | Requisitos |
|---|---|---|
| `scripts/01-keyspace.cql` | Keyspace, estrategia y factor de replicación | RF2 |
| `scripts/02-tablas.cql` | Las 4 tablas y el índice secundario, con la justificación de cada clave | RF4, RF5, RF6, RF7, RF10 |
| `scripts/03-carga-muestra.cql` | Muestra idempotente de 35 comentarios | RF11, RNF7 |
| `scripts/04-crud.cql` | CREATE (batch sobre tablas duplicadas), READ puntual, UPDATE, UPDATE condicional (LWT), incremento de counters, DELETE | RF8 |
| `scripts/05-consultas.cql` | Q1, Q1b, Q2, Q3, Q4 y la comparativa del índice secundario | RF9, RF10 |
| `scripts/06-medicion.cql` | Versión observada, conteos, distribución por token y `TRACING` comparativo | RF12, RF13, RNF9 |

Todas las sentencias están comentadas y separadas por propósito (RNF6).

---

## 7. Rendimiento y distribución

La plantilla de resultados, con fecha de ejecución, versión observada de
Cassandra y recursos del equipo, está en [`evidencia.md`](evidencia.md).

**Método de medición** (obligatorio declararlo según la sección 6 del enunciado):

1. **Carga por `COPY`** (`tools/carga_masiva.sh`): mide la tasa de ingesta
   extremo a extremo, incluyendo parseo de CSV. Es la cota inferior realista.
2. **`cassandra-stress` con perfil propio** (`tools/benchmark_escritura.sh` +
   `tools/stress_comentarios.yaml`): escribe directamente sobre
   `comentarios_por_partido`, con la misma clave de partición y la misma
   distribución de particiones. Reporta *op rate*, latencia media y percentil 99.
3. **`nodetool tablestats` / `tablehistograms`**: tamaño máximo de partición,
   celdas vivas por *slice* y tombstones por lectura.

**Limitaciones conocidas del ambiente de prueba**, que deben acompañar cualquier
número reportado:

- Un solo nodo: no hay paralelismo entre réplicas ni coordinación real.
- `RF=1` y `CL=ONE`: no se mide el costo de un quórum distribuido.
- El cliente (`cassandra-stress` o `cqlsh`) corre en el mismo contenedor y
  compite por la misma CPU que el servidor.
- Heap de 2 GB fijado en el Compose; el almacenamiento es el disco de la
  notebook a través del bind mount de Docker Desktop, que en macOS y Windows
  agrega una capa de virtualización con penalidad de E/S significativa.

**Resultado obtenido en la notebook de referencia** (Apple M1 Pro, 8 núcleos,
16 GB, Docker con 7,7 GB, Cassandra 5.0.9 — detalle completo en
[`evidencia.md`](evidencia.md)):

| Medición | Resultado |
|---|---|
| `cassandra-stress`, 300.000 escrituras, 64 hilos | **14.757 op/s**, 0 errores, latencia mediana 1,6 ms, p99 17,1 ms |
| `COPY` de 1.000.000 de filas | 20,2 s → **49.490 filas/s**, 0 filas omitidas |
| Distribución entre los 4 shards de una ventana | 155 / 152 / 142 / 140 → desvío máximo +5,3 % |
| Tamaño máximo de partición | 20.501 bytes |
| Q1 con clave de partición (tracing) | 1 partición, 2.116 µs |
| Índice secundario sin clave de partición (tracing) | 17 rangos, 17.035 µs → **8× más lento** |

El objetivo de 10.000 escrituras/s del RF12 **se alcanzó** en este hardware. El
factor que limitó la cola de latencia fueron las pausas de GC sobre el heap de
2 GB fijado en el Compose. En otra máquina el resultado puede ser distinto: el
enunciado exige documentar la tasa **real** observada y sus condiciones, no
declararla, así que cada integrante que reproduzca el hito debe volver a
completar la evidencia con sus propios números.

---

## 8. Coherencia con el TPO

| Vínculo | Cómo se mantiene |
|---|---|
| **Hito 1 (requisitos)** | El volumen de comentarios y la concurrencia durante los partidos populares provienen del análisis de usuarios del Hito 1. Los 64 equipos y el calendario definen la cardinalidad de `id_partido`. |
| **Hito 2 (matriz de decisión)** | La matriz ya había identificado que el flujo de comentarios no encaja en un motor documental ni en un grafo, por ser escritura intensiva con patrones de lectura fijos. Este hito materializa esa conclusión. |
| **Hito 3 (arquitectura distribuida)** | Cassandra ocupa el rol de almacén de alta ingesta previsto en la arquitectura. El keyspace RF=1 del laboratorio es la reducción local del despliegue multi-DC descrito allí. |
| **Hito 4 (MongoDB)** | `id_usuario` y `equipo_apoyado` referencian las entidades del modelo documental. Los códigos de equipo son los mismos `codigo_iso` de la colección `equipos`. Cassandra **no** replica los datos de equipos ni de jugadores: los referencia. |
| **Hito 5 (Neo4j)** | `id_partido` usa el mismo identificador (`P-001`, `P-002`, …) que el nodo `:Partido` del grafo. Un comentario puede así vincularse al partido, su sede y sus equipos sin duplicar esa información en Cassandra. |

**Qué cambiaría si el módulo debiera servir reportes analíticos históricos**
(pregunta guía 12): nada dentro de Cassandra. Consultas como "los 10 usuarios
más reportados del torneo" o "evolución del sentimiento por confederación" son
agregaciones globales no acotadas por clave de partición, exactamente lo que
Cassandra no hace. La solución correcta es exportar periódicamente
`comentarios_por_partido` a un almacén columnar analítico y consultarlo allí,
manteniendo Cassandra como el almacén operativo de baja latencia.

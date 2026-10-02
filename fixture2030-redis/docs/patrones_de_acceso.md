# Hito 7 — Patrones de Acceso del Módulo de Caché y Sesiones (Redis)

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Problema de concurrencia**, **Patrones de
acceso** y **Coherencia con el TPO** de la sección 8 del enunciado (RF2). Los
patrones se definieron antes que las claves: cada clave de
[`modelo_clave_valor.md`](modelo_clave_valor.md) sale de uno de estos patrones.

---

## 1. Problema de concurrencia

Durante el Mundial millones de usuarios entran a la plataforma al mismo tiempo,
sobre todo cuando juega una selección popular. El problema no es la cantidad de
datos sino la cantidad de **lecturas repetidas** del mismo dato y de
**actualizaciones simultáneas** sobre el mismo contador.

**Supuestos de carga declarados** (estimaciones del equipo, base de las
decisiones):

| Supuesto | Valor asumido |
|---|---|
| Sesiones activas en el pico (partido popular) | 500.000 |
| Peticiones de un usuario activo | 1 cada 30 s aprox. |
| Peticiones por segundo que validan sesión | ≈ 16.000 (500.000 / 30 s) |
| Lecturas por segundo de la ficha de un partido popular | ≈ 20.000 |
| Cambios en la ficha de un partido (gol, tarjeta, fin) | ~10 a 20 por partido |
| Lecturas por segundo de la ficha de un equipo | ≈ 2.000 |
| Cambios en los datos de un equipo | muy pocos por semana |
| Votos por segundo en la encuesta de figura (pico, fin del partido) | ≈ 5.000 |

Con estos números:

* Validar la sesión contra MongoDB o Neo4j en cada petición cargaría a la
  fuente de verdad con miles de lecturas por segundo de un dato que es
  **temporal** y no tiene valor de negocio.
* La ficha de un partido se lee miles de veces por cada vez que cambia. Es el
  caso ideal de caché: muchas lecturas, pocas escrituras.
* El contador de visitas y la encuesta reciben miles de actualizaciones por
  segundo **sobre la misma clave**. Si la aplicación hiciera "leer → sumar →
  guardar", dos usuarios podrían leer el mismo valor y uno de los votos se
  perdería.

## 2. Patrones de acceso

Se definieron seis patrones. Para cada uno se indica quién lo usa, con qué dato
se encuentra, qué recibe el consumidor, la frecuencia, si el dato es temporal o
pertenece a una fuente de verdad, y la estructura elegida.

### PA1 — Validar y renovar la sesión del usuario

| Aspecto | Decisión |
|---|---|
| Quién | La aplicación, en cada petición de un usuario logueado |
| Dato de entrada | `id_sesion` (viene en la cookie del navegador / app) |
| Respuesta | Usuario, rol y estado de la sesión, o "no existe" → volver al login |
| Frecuencia | Lectura muy alta (≈ 16.000/s); escritura en cada petición (renovación) |
| Temporal / verdad | **Temporal.** La sesión solo existe en Redis. El usuario (perfil) vive en otro módulo |
| Estructura | **Hash**: tiene varios atributos que se leen y se actualizan por separado (`HGET`, `HINCRBY`) sin reescribir todo |

### PA2 — Crear y cerrar la sesión (login / logout / invalidación)

| Aspecto | Decisión |
|---|---|
| Quién | La aplicación al hacer login o logout; un moderador o admin al suspender a un usuario |
| Dato de entrada | `id_sesion` |
| Respuesta | Confirmación de creación o de borrado |
| Frecuencia | Media (picos al inicio de cada partido) |
| Temporal / verdad | **Temporal** |
| Estructura | El mismo **Hash** de PA1, creado con `HSET` + `EXPIRE` y borrado con `DEL` |

### PA3 — Consultar la ficha de un partido

| Aspecto | Decisión |
|---|---|
| Quién | Hinchas que abren la ficha del partido (resultado, sede, equipos) |
| Dato de entrada | `codigo_partido` (ej. `P-001`) |
| Respuesta | JSON con fecha, fase, equipos, sede y goles |
| Frecuencia | Lectura muy alta (≈ 20.000/s en partidos populares); cambia pocas veces |
| Temporal / verdad | **Copia en caché.** La fuente de verdad es **Neo4j** (Hito 5, nodos `Partido`, `Equipo`, `Sede`) |
| Estructura | **String** con el JSON serializado: siempre se lee la ficha entera, no hace falta leer campos sueltos |

### PA4 — Consultar la ficha de un equipo

| Aspecto | Decisión |
|---|---|
| Quién | Hinchas que abren la página de una selección |
| Dato de entrada | `codigo_iso` (ej. `ARG`) |
| Respuesta | JSON con nombre, confederación, grupo, DT y ranking |
| Frecuencia | Lectura alta; cambia muy poco |
| Temporal / verdad | **Copia en caché.** La fuente de verdad es **MongoDB** (Hito 4, colección `equipos`) |
| Estructura | **String** con el JSON serializado, por el mismo motivo que PA3 |

### PA5 — Contar visitas y usuarios conectados a un partido

| Aspecto | Decisión |
|---|---|
| Quién | La aplicación cada vez que un usuario abre o deja la transmisión de un partido |
| Dato de entrada | `codigo_partido` y, para conectados, `usuario_id` |
| Respuesta | Número de visitas; cantidad de usuarios conectados |
| Frecuencia | Escritura muy alta y concurrente sobre la misma clave |
| Temporal / verdad | **Temporal.** Es una métrica de actividad en vivo |
| Estructura | **String entero** para visitas (`INCR`); **Set** para conectados (`SADD`/`SREM`/`SMEMBERS`), porque un usuario no debe contarse dos veces |

### PA6 — Votar y ver el ranking de la encuesta "figura del partido"

| Aspecto | Decisión |
|---|---|
| Quién | Hinchas que votan; la app que muestra el Top 3 |
| Dato de entrada | `codigo_partido` y `id_jugador` votado (ej. `ARG-10`) |
| Respuesta | Top 3 de jugadores con su cantidad de votos |
| Frecuencia | Escritura muy alta al final del partido; lectura alta del Top |
| Temporal / verdad | **Temporal mientras la encuesta está abierta.** Al cerrar, el resultado final se guarda en la fuente de verdad |
| Estructura | **Sorted Set**: `ZINCRBY` suma el voto de forma atómica y el conjunto ya queda ordenado por score para `ZREVRANGE` (RF9) |

### Resumen

| Patrón | Clave | Tipo | TTL |
|---|---|---|---|
| PA1, PA2 | `sesion:<id_sesion>` | Hash | 1800 s, renovado con actividad |
| PA3 | `cache:partido:<codigo_partido>` | String (JSON) | 300 s + invalidación con `DEL` |
| PA4 | `cache:equipo:<codigo_iso>` | String (JSON) | 3600 s + invalidación con `DEL` |
| PA5 | `contador:partido:<codigo_partido>:visitas` | String (entero) | 172800 s (48 h) |
| PA5 | `conectados:partido:<codigo_partido>` | Set | 10800 s (3 h) |
| PA6 | `encuesta:partido:<codigo_partido>:figura` | Sorted Set | sin TTL abierta; 86400 s al cerrar |

## 3. Coherencia con el TPO

Redis **no reemplaza** ninguno de los módulos anteriores; se pone delante de
ellos para las lecturas repetidas y guarda el estado temporal que no tiene
sentido guardar en una base persistente.

| Módulo anterior | Qué guarda (fuente de verdad) | Relación con Redis |
|---|---|---|
| MongoDB (Hito 4) | Equipos y jugadores | `cache:equipo:<iso>` es una copia de `equipos`. Los ids de jugador de la encuesta (`ARG-10`) son los `_id` de `jugadores` |
| Neo4j (Hito 5) | Partidos, sedes, eventos y relaciones | `cache:partido:<id>` es una copia de la ficha del partido (`P-001`, `P-002` son los mismos códigos) |
| Cassandra (Hito 6) | Comentarios masivos | No se cachean comentarios: ya están modelados para lectura rápida por partición. La sesión de Redis es la que identifica al usuario que comenta |

Con respecto a los requisitos de rendimiento del TPO, este módulo resuelve las
lecturas de baja latencia (sesión y fichas) y los contadores en vivo, que son
justamente los accesos que no conviene mandar a una base con disco en cada
petición. Las cifras medidas en el laboratorio están en
[`evidencia/README.md`](evidencia/README.md).

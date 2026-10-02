# Hito 7 — Modelo Clave/Valor

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Modelo clave/valor**, **Datos cargados** y
**Operaciones Redis** de la sección 8 del enunciado. Cada clave está vinculada a
un patrón de [`patrones_de_acceso.md`](patrones_de_acceso.md) (RNF4).

---

## 1. Convención de nombres (RNF5)

Formato general:

```text
<dominio>[:<entidad>]:<identificador>[:<propósito>]
```

* Las partes se separan con `:` (convención vista en clase; Redis no crea
  carpetas, es solo para que el nombre se entienda).
* El **primer segmento** dice el dominio o propósito: `sesion`, `cache`,
  `contador`, `conectados`, `encuesta`.
* La **entidad** dice a qué objeto del Fixture pertenece el dato (`partido`,
  `equipo`). Se omite solo cuando el dominio ya es la entidad: en
  `sesion:<id_sesion>` la sesión es el propio dato.
* El **propósito** aparece cuando una misma entidad tiene varios datos del
  mismo dominio: `contador:partido:P-001:visitas`,
  `encuesta:partido:P-001:figura`.
* El **identificador** es siempre un código estable que no cambia al editar
  datos: `S-0001`, `P-001`, `ARG`. Nunca se usa un nombre ("Argentina") ni un
  token como parte de la clave.
* El **alcance** queda explícito: `contador:partido:P-001:visitas` es un
  contador de un partido, no uno global.
* Todo lo que empieza con `cache:` es una copia descartable que se puede
  reconstruir desde su fuente de verdad. Lo que no empieza con `cache:` es
  estado temporal que vive solo en Redis.

## 2. Claves del módulo

| Clave | Tipo | Patrón | Operaciones | TTL / ciclo de vida |
|---|---|---|---|---|
| `sesion:<id_sesion>` | Hash | PA1, PA2 | `HSET`, `HGETALL`, `HGET`, `HINCRBY`, `EXPIRE`, `TTL`, `DEL` | 1800 s, se renueva con cada petición válida |
| `cache:partido:<codigo_partido>` | String (JSON) | PA3 | `GET`, `SET ... EX`, `DEL` | 300 s; `DEL` cuando cambia el partido en Neo4j |
| `cache:equipo:<codigo_iso>` | String (JSON) | PA4 | `GET`, `SET ... EX`, `DEL` | 3600 s; `DEL` cuando cambia el equipo en MongoDB |
| `contador:partido:<codigo_partido>:visitas` | String (entero) | PA5 | `INCR`, `INCRBY`, `EXPIRE`, `GET` | 172800 s (48 h) desde la última visita |
| `conectados:partido:<codigo_partido>` | Set | PA5 | `SADD`, `SREM`, `SISMEMBER`, `SMEMBERS`, `EXPIRE` | 10800 s (3 h) desde el último ingreso |
| `encuesta:partido:<codigo_partido>:figura` | Sorted Set | PA6 | `ZADD`, `ZINCRBY`, `ZREVRANGE` | sin TTL mientras está abierta; 86400 s al cerrarla |

No hay ninguna otra clave en el módulo. Solo para las pruebas se crean,
siempre con TTL corto:

* `bench:*` en `tools/medicion.sh` (se borran al final);
* `contador:partido:P-999:visitas` en `tools/prueba_concurrencia.sh` (TTL 600 s);
* `cache:prueba:ttl` en `cache.redis`, para mostrar que `SET` sin `EX` borra
  el TTL (se borra en el mismo script).

## 3. Atributos de la sesión (RF5)

`sesion:<id_sesion>` es un Hash con estos campos:

| Campo | Ejemplo | Para qué sirve |
|---|---|---|
| `id_sesion` | `S-0001` | Identifica la sesión (es el mismo valor que la clave) |
| `usuario_id` | `U-0001` | Usuario asociado. El perfil completo está en otro módulo |
| `rol` | `fan`, `periodista`, `moderador`, `admin` | Permisos dentro de la plataforma |
| `estado` | `activa` | Estado de acceso. Mientras la clave existe vale `activa`; el cierre y la suspensión borran la clave en lugar de cambiar este campo, así que es informativo |
| `dispositivo` | `web`, `android`, `ios` | Información temporal útil para soporte |
| `creada_en` | `2030-06-10T20:00:00Z` | Momento del login |
| `ultimo_acceso` | `2030-06-10T20:15:00Z` | Momento de la última actividad |
| `paginas_vistas` | `2` | Contador de actividad de la sesión (`HINCRBY`) |

Además, el **TTL de la clave** es el atributo temporal más importante: indica
cuánto falta para que la sesión venza por inactividad.

**Regla de validez:** la sesión es válida si `HGET sesion:<id> usuario_id`
devuelve un valor. Se valida por ese campo y no solo por la existencia de la
clave por el caso explicado en `ciclo_de_vida_e_invalidacion.md` §1.

**No se guardan** tokens, contraseñas ni datos personales (RNF7). El
`id_sesion` es un identificador opaco generado por la aplicación.

Se eligió **Hash** y no un String con JSON porque en cada petición se
modifican solo dos campos (`ultimo_acceso` y `paginas_vistas`). Con un String
habría que leer todo el JSON, modificarlo en la aplicación y volver a
escribirlo, que es justamente el antipatrón de "leer → modificar → escribir".

## 4. Por qué cada estructura

| Estructura | Uso en el módulo | Por qué |
|---|---|---|
| String (JSON) | Fichas de partido y equipo | Se leen enteras y se reemplazan enteras. `SET ... EX` guarda el valor y el TTL en un solo comando |
| String (entero) | Visitas | `INCR` es atómico |
| Hash | Sesión | Campos que se leen y modifican por separado |
| Set | Usuarios conectados | Miembros únicos: un usuario conectado desde dos pestañas cuenta una vez |
| Sorted Set | Encuesta | Suma atómica con `ZINCRBY` y orden automático por votos para el Top N |

No se usaron Lists porque ningún patrón necesita una secuencia por orden de
inserción.

## 5. Datos cargados

El conjunto de datos es pequeño, escrito a mano en
`scripts/carga_muestra.redis` y **reproducible**: el script es idempotente y
siempre deja el mismo estado.

| Tipo de dato | Cantidad | Detalle |
|---|---|---|
| Sesiones | 10 | `S-0001` a `S-0010`, usuarios `U-0001` a `U-0010`. 7 `fan`, 1 `periodista`, 1 `moderador`, 1 `admin`. Dispositivos: 6 web, 2 android, 2 ios |
| Caché de partidos | 1 | `P-001` (ARG–ESP), el mismo del Hito 5. `P-002` (URU–ARG) existe en Neo4j pero no se carga, para mostrar el cache miss |
| Caché de equipos | 4 | `ARG`, `BRA`, `URU`, `ESP`, con los mismos datos de `equipos.json` del Hito 4 |
| Contador de visitas | 1 | `P-001`, inicia en 0 |
| Conectados | 1 Set, 6 miembros | `U-0001` a `U-0006` conectados a `P-001` |
| Encuesta | 1 Sorted Set, 4 jugadores | `ARG-10`, `ARG-9`, `ESP-8`, `ESP-7` con 0 votos |

Total después de la carga: **18 claves**, 17 con TTL (todas salvo la encuesta
abierta). Se verifica con `INFO keyspace` → `keys=18,expires=17`.

El script de sesiones crea además sesiones de prueba (`S-0100`, `S-0101`,
`S-0199`) y el de caché carga `P-002` en el camino del miss. La prueba de
concurrencia usa `P-999`.

## 6. Operaciones Redis (scripts)

Los scripts están en `scripts/` y se ejecutan con `redis-cli` dentro del
contenedor (ver el README). Están separados por propósito (RNF9):

| Script | Propósito |
|---|---|
| `inicializacion.redis` | `PING`, versión (`INFO server`), persistencia (`INFO persistence`), límite y política de memoria (`INFO memory`) |
| `carga_muestra.redis` | Carga el conjunto de datos de la sección 5 |
| `sesiones.redis` | Crear, recuperar, actualizar, renovar, cerrar, invalidar y expirar sesiones |
| `cache.redis` | Cache hit, cache miss, invalidación por cambio en la fuente de verdad |
| `concurrencia.redis` | `INCR` y `SADD` con `EXPIRE` en `MULTI/EXEC`, `ZINCRBY`, ranking Top 3, `SREM` y actividad de sesión |
| `metricas.redis` | `INFO stats/memory/keyspace`, `SCAN` y TTL observados |
| `limpieza.redis` | Borra las claves del módulo por nombre (opcional) |

Herramientas en `tools/`:

| Herramienta | Propósito |
|---|---|
| `prueba_concurrencia.sh` | N clientes `redis-cli` en paralelo haciendo `INCR` sobre el mismo contador |
| `medicion.sh` | Tiempo de N comandos de cada operación principal, con `redis-cli` |
| `generar_evidencia.sh` | Ejecuta todo en orden y guarda las salidas en `docs/evidencia/` |

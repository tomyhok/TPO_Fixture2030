# Hito 7 — Ciclo de Vida, Caché e Invalidación

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Ciclo de vida**, **Fuente de verdad y
caché** y **Concurrencia** de la sección 8 del enunciado (RF3, RF4, RF6, RF7,
RF8 y RNF6).

---

## 1. Ciclo de vida de una sesión

```text
 login                petición válida              30 min sin actividad
───────► [ ACTIVA ] ──────────────────► [ ACTIVA ] ─────────────────────► (Redis la borra)
 HSET + EXPIRE 1800    HINCRBY + HSET +       │
 (MULTI/EXEC)          EXPIRE 1800            │ logout / suspensión
                       (MULTI/EXEC)           └──────────────────────────► DEL
```

| Etapa | Qué hace la aplicación | Comandos |
|---|---|---|
| Creación | Al hacer login genera un `id_sesion` y guarda la sesión con TTL | `MULTI` · `HSET sesion:<id> ...` · `EXPIRE sesion:<id> 1800` · `EXEC` |
| Validación | En cada petición busca la sesión por su id | `HGET sesion:<id> usuario_id` (o `HGETALL`) |
| Renovación | Si la sesión existe, actualiza la actividad y renueva el TTL | `MULTI` · `HINCRBY ... paginas_vistas 1` · `HSET ... ultimo_acceso` · `EXPIRE ... 1800` · `EXEC` |
| Expiración | Si pasan 30 min sin peticiones, Redis borra la clave solo | Nativo (`EXPIRE`); se comprueba con `TTL` = -2 |
| Cierre | Logout del usuario | `DEL sesion:<id>` |
| Invalidación explícita | Un moderador o admin suspende al usuario | `DEL sesion:<id>` |

### Decisiones

* **Regla de validez:** una sesión es válida **si `HGET sesion:<id> usuario_id`
  devuelve un valor**. No hace falta comparar fechas en la aplicación: si
  venció, Redis ya la borró y `HGET` devuelve vacío.
* **Por qué se valida con `usuario_id` y no solo con la existencia de la
  clave:** la validación y el `MULTI/EXEC` de renovación son dos pasos. Si la
  sesión vence justo entre los dos, `HINCRBY` y `HSET` vuelven a crear un Hash
  que solo tiene `paginas_vistas` y `ultimo_acceso` (con TTL, porque el
  `EXPIRE` va en el mismo `MULTI`). Ese Hash no tiene `usuario_id`, así que la
  próxima petición no lo acepta como sesión y el usuario va al login. El Hash
  incompleto vence solo a los 30 minutos.
* **Duración: 1800 s (30 minutos) de inactividad.** Un partido dura unos 120
  minutos y el usuario interactúa cada pocos minutos (cambia de pestaña, vota,
  comenta). 30 minutos cubren el entretiempo (15 min) con margen, y a la vez no
  dejan sesiones abiertas horas en un dispositivo que el usuario abandonó. Las
  sesiones tienen permisos (moderador, admin), así que no conviene que duren
  más de lo necesario.
* **Evento que renueva:** solo una **petición iniciada por el usuario**
  (navegar, votar, comentar). Las actualizaciones automáticas en segundo plano
  de la app (por ejemplo, refrescar el marcador) **no** renuevan, porque si no
  una pestaña olvidada mantendría la sesión viva para siempre.
* **Por qué MULTI/EXEC:** `HSET` no renueva el TTL (se ve en el paso 3 de
  `sesiones.redis`: después del `HSET` el TTL sigue en 1200). Por eso la
  actualización y el `EXPIRE` se mandan juntos. Con `MULTI/EXEC` otro cliente no
  puede meter comandos en el medio y nunca queda una sesión creada sin TTL.
* **No hay proceso de limpieza:** no se recorren las sesiones buscando las
  vencidas. Redis las elimina de forma pasiva (cuando alguien accede) y activa
  (muestreo periódico). En la evidencia se ve `expired_keys_active:1`.
* **Consecuencia de una sesión vencida o inexistente:** `HGETALL` devuelve
  vacío y `TTL` devuelve -2. La aplicación responde "no autorizado" y manda al
  usuario al login. No se pierde ningún dato de negocio, porque la sesión no
  guarda nada que no esté en otro módulo; lo único que pasa es que hay que
  volver a iniciar sesión.

### Cómo se comprueba

| Situación | Resultado de `TTL sesion:<id>` |
|---|---|
| Sesión activa | Segundos restantes (≤ 1800) |
| Clave sin expiración (no debería pasar nunca) | -1 |
| Sesión vencida, cerrada o inexistente | -2 |

## 2. Otros datos temporales (RNF6)

Todos los datos del módulo tienen una decisión de ciclo de vida:

| Clave | Decisión | Justificación |
|---|---|---|
| `cache:partido:<id>` | TTL 300 s + `DEL` al cambiar | Ver sección 3 |
| `cache:equipo:<iso>` | TTL 3600 s + `DEL` al cambiar | Ver sección 3 |
| `contador:partido:<id>:visitas` | Cada visita hace `INCR` + `EXPIRE 172800` en `MULTI/EXEC`: el contador vence 48 h después de la última visita | `INCR` no pone ni renueva TTL, y si la clave había vencido la crea **sin** TTL. Al mandar el `EXPIRE` en la misma transacción nunca queda un contador permanente. Interesa durante el partido y el día siguiente |
| `conectados:partido:<id>` | Cada ingreso hace `SADD` + `EXPIRE 10800` en `MULTI/EXEC` (3 h desde el último ingreso). Cuando el usuario sale se hace `SREM` | Mismo motivo que el contador: `SADD` sobre una clave vencida la crea sin TTL. 3 h cubren previa + partido + post |
| `encuesta:<id>:figura` | **Sin TTL** mientras está abierta. Al cerrar: se guarda el resultado en la fuente de verdad y se pone `EXPIRE 86400` | Si tuviera TTL podría vencer o ser elegida para evicción (`volatile-lru`) en medio de la votación. Después del cierre queda 24 h para mostrar el resultado |

## 3. Fuente de verdad y caché (patrón Cache-Aside)

Se aplica el patrón **Cache-Aside** visto en clase: la aplicación decide cuándo
leer de Redis, cuándo cargar desde la base y cuándo invalidar. Redis no sabe
nada de lo que cambia en MongoDB o Neo4j.

| Dato | Fuente de verdad | Clave en caché | TTL máximo |
|---|---|---|---|
| Ficha de partido | Neo4j (Hito 5) | `cache:partido:<codigo_partido>` | 300 s |
| Ficha de equipo | MongoDB (Hito 4) | `cache:equipo:<codigo_iso>` | 3600 s |

### Lectura

```text
clave = "cache:partido:" + codigo_partido
valor = GET clave
SI valor existe:
    responder valor                       # cache hit
SINO:                                     # cache miss
    valor = consultar Neo4j
    SET clave valor EX 300
    responder valor
```

* **Cache hit:** `GET` devuelve el JSON (paso 1 de `cache.redis`).
* **Cache miss:** `GET` devuelve `(nil)`. La app consulta la fuente de verdad,
  guarda la copia con `SET ... EX` y responde (paso 2).
* Siempre se usa `SET ... EX`: un `SET` sin `EX` borra el TTL y la copia
  quedaría para siempre (paso 5 de `cache.redis`, TTL pasa a -1).

### Actualización e invalidación

```text
actualizar la fuente de verdad (Neo4j o MongoDB)
DEL clave
```

* Primero se actualiza la base y **después** se borra la copia. La próxima
  lectura es un miss y trae el dato nuevo (paso 3 de `cache.redis`: el gol de
  Argentina pasa de 0-0 a 1-0).
* Se borra en vez de reescribir porque es más simple: solo hay un lugar que
  carga la caché (el camino del miss).
* **No se depende solo del TTL.** Sin el `DEL`, un gol se vería con hasta 5
  minutos de atraso. El TTL es un **límite de seguridad**: si por algún error
  la invalidación no se ejecuta, la copia vieja dura como máximo 300 s
  (partido) o 3600 s (equipo).

### Período máximo de una copia

* **Partido: 300 s.** Durante el partido el resultado cambia; cada cambio
  invalida la clave, así que el TTL solo actúa si falla la invalidación. 5
  minutos de atraso es lo máximo que aceptamos en ese caso.
* **Equipo: 3600 s.** Los datos de un equipo (DT, grupo, ranking) casi no
  cambian durante el torneo. Una hora reduce las lecturas a MongoDB y el riesgo
  de ver un dato viejo es bajo.

Caso límite conocido: si un usuario tuvo un miss justo antes de la
actualización y escribe en Redis justo después del `DEL`, puede quedar
guardada la versión vieja. En ese caso el TTL limita el problema a 300 s. Para
este trabajo lo aceptamos y lo dejamos documentado.

### Si Redis no tiene la clave o no está disponible

* **No tiene la clave** (venció, se invalidó o fue eliminada por memoria):
  es un cache miss normal, se lee la fuente de verdad. Por eso cualquier clave
  `cache:` tiene que poder reconstruirse.
* **Redis caído:**
  * Fichas de partido y equipo: la app lee directamente de Neo4j / MongoDB. Va
    más lento y carga más esas bases, pero el usuario sigue viendo datos
    correctos.
  * Sesiones: no se pueden validar. Los usuarios tienen que volver a iniciar
    sesión cuando Redis vuelva. Con la persistencia AOF del Compose, un
    reinicio normal del contenedor **no** borra las sesiones (ver
    `evidencia/11_persistencia.txt`).
  * Contadores y encuesta: se pierden las actualizaciones mientras Redis esté
    caído.

## 4. Concurrencia (RF8)

### Operaciones que necesitan atomicidad

| Operación | Riesgo si se hiciera mal | Cómo se resuelve |
|---|---|---|
| Visitas de un partido | Dos clientes hacen `GET` 10, suman 1 y hacen `SET` 11: se pierde una visita | `INCR` (un solo comando, Redis lo ejecuta sin intercalar), junto con su `EXPIRE` en `MULTI/EXEC` |
| Voto en la encuesta | Igual que arriba: se pierden votos | `ZINCRBY` (un solo comando) |
| Usuarios conectados | Un usuario contado dos veces | `SADD` / `SREM` sobre un Set (miembros únicos) |
| Actividad de la sesión | Dos pestañas actualizan a la vez; o la sesión queda actualizada pero sin renovar el TTL | `HINCRBY` atómico + `MULTI/EXEC` para actualizar y renovar juntos |
| Creación de sesión | La app se corta entre `HSET` y `EXPIRE` y queda una sesión sin TTL | `MULTI/EXEC` |

### Por qué no se pierden actualizaciones

* Un comando de Redis se ejecuta completo antes de empezar el siguiente. Como
  `INCR` y `ZINCRBY` leen y suman **dentro del servidor**, no existe el momento
  en que dos clientes leen el mismo valor viejo.
* `MULTI/EXEC` encola los comandos y los ejecuta todos seguidos, sin que otro
  cliente se meta en el medio. Redis **no tiene rollback**: si un comando falla
  (por ejemplo, `HINCRBY` sobre una clave que no es un Hash), los demás se
  ejecutan igual. Por eso cada clave del módulo tiene un solo tipo de dato fijo
  según su prefijo, y `paginas_vistas` siempre se carga como número.

### Evidencia

`tools/prueba_concurrencia.sh` lanza varios `redis-cli` en paralelo, cada uno
con su propia conexión, haciendo `INCR` sobre el mismo contador:

| Clientes | `INCR` por cliente | Esperado | Obtenido |
|---|---|---|---|
| 10 | 1.000 | 10.000 | 10.000 |
| 20 | 5.000 | 100.000 | 100.000 |

No se perdió ninguna actualización. Salida completa en
[`evidencia/08_prueba_concurrencia.txt`](evidencia/08_prueba_concurrencia.txt).
`ZINCRBY` funciona con el mismo principio (suma dentro del servidor en un solo
comando).

Limitación: la encuesta no impide que un mismo usuario vote dos veces. Eso
necesitaría un control adicional (por ejemplo un Set de votantes) y lo dejamos
fuera del alcance de este hito.

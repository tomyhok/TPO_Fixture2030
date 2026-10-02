# Hito 7 — Memoria y Escalabilidad

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre el apartado **Memoria y escalabilidad** de la sección 8 del
enunciado (RF10) y la explicación del nodo único pedida en 5.1.

---

## 1. Configuración elegida

En el `docker-compose.yml`:

```text
--maxmemory 256mb
--maxmemory-policy volatile-lru
```

Se verifica con `INFO memory` en `scripts/inicializacion.redis`:

```text
maxmemory_human:256.00M
maxmemory_policy:volatile-lru
```

* **256 MB** es el mismo valor del ejemplo de clase: un límite chico, acorde a
  una notebook. Alcanza de sobra para la muestra (se midieron ~1,9 MB usados).
  Se configura al arrancar en el Compose en lugar de con `CONFIG SET`, para
  que no se pierda si se recrea el contenedor.
* **`volatile-lru`**: cuando se llega al límite, Redis elimina las claves
  **con TTL** que se usaron hace más tiempo. Las claves sin TTL no se tocan.

## 2. Por qué `volatile-lru`

En la misma instancia conviven copias de caché (descartables) y estado
temporal (sesiones, contadores, encuesta). Comparamos las políticas vistas en
clase:

| Política | Qué pasaría en este módulo | ¿La elegimos? |
|---|---|---|
| `noeviction` | Al llenarse, Redis rechaza escrituras: no se pueden crear sesiones nuevas ni guardar caché. Nadie más puede entrar a la plataforma | No |
| `allkeys-lru` | Puede borrar cualquier clave, incluida la encuesta abierta, y se perderían votos | No |
| `allkeys-lfu` | Mismo problema que `allkeys-lru` con la encuesta | No |
| `volatile-ttl` | Borra primero las claves con menos TTL restante. Las fichas de partido (300 s) serían siempre las primeras, aunque sean las más leídas | No |
| **`volatile-lru`** | Solo borra claves con TTL, empezando por las menos usadas. La encuesta abierta (sin TTL) queda protegida | **Sí** |

La idea es usar el TTL como marca de "esto se puede descartar". En nuestro
modelo **todas** las claves tienen TTL salvo la encuesta mientras está abierta.
Se ve en `INFO keyspace`: `keys=18,expires=17` después de la carga (la encuesta
abierta es la única sin TTL) y `keys=19,expires=19` al final de la corrida,
cuando la encuesta ya estaba cerrada. Para que esto se mantenga, el contador y
el Set de conectados reciben su `EXPIRE` en el mismo `MULTI/EXEC` que el `INCR`
o el `SADD` (ver `ciclo_de_vida_e_invalidacion.md` §2).

Riesgo de esta política: si todas las claves sin TTL llenaran la memoria,
`volatile-lru` no tendría nada para borrar y se comportaría como `noeviction`.
En nuestro caso solo hay una encuesta abierta por partido, así que eso no
debería pasar.

## 3. TTL vs. evicción

Son dos mecanismos distintos:

* **TTL (expiración):** lo decidimos nosotros por cada dato. Responde a "¿hasta
  cuándo es válido o seguro este dato?". Se ve en `expired_keys`.
* **Evicción:** la decide Redis cuando no tiene más memoria. Responde a "¿qué
  puedo sacrificar para seguir aceptando escrituras?". Se ve en
  `evicted_keys`.

Una clave con TTL puede desaparecer **antes** de su vencimiento si Redis la
elige para evicción. Efecto sobre cada tipo de dato:

| Dato | Si vence por TTL | Si se elimina por evicción |
|---|---|---|
| `cache:partido`, `cache:equipo` | Cache miss → se recarga de la fuente de verdad. Comportamiento esperado | Igual: cache miss y recarga. Sin impacto en los datos |
| `sesion:` | El usuario estuvo 30 min inactivo y vuelve al login. Comportamiento esperado | Un usuario **activo** pierde su sesión y tiene que volver a loguearse. Molesto pero no se pierde información |
| `contador:...:visitas` | Ya pasaron 48 h, no se usa más | Se pierde el conteo. Es una métrica en vivo, se acepta |
| `conectados:partido:` | Ya terminó el partido | Se pierde el conteo de conectados hasta que los usuarios vuelvan a entrar |
| `encuesta:...:figura` (abierta) | No tiene TTL | No se elimina (protegida por `volatile-lru`) |

En la corrida del laboratorio: `expired_keys:1` (la sesión de prueba de 5 s) y
`evicted_keys:0`. Nunca se llegó al límite de memoria.

Si en producción `evicted_keys` empezara a subir, la señal sería que la
instancia necesita más memoria, no que hay que acortar los TTL.

## 4. Persistencia

Igual que el laboratorio de clase, el Compose activa:

* **AOF** (`--appendonly yes`): registra las escrituras para reconstruir el
  estado al reiniciar.
* **RDB** (`--save 60 1`): snapshot si hubo al menos 1 cambio en 60 s.

Los archivos quedan en `~/docker/data/redis` (RNF2). En la evidencia
(`evidencia/11_persistencia.txt`) se reinició el contenedor y las 19 claves
seguían ahí, con su TTL corriendo.

Que Redis persista no lo convierte en fuente de verdad: las fichas siguen
siendo copias y la fuente de verdad sigue siendo MongoDB y Neo4j.

## 5. Límites del nodo local

El ambiente es **un único nodo** (standalone). Sirve para aprender el modelo y
los comandos, pero:

* Es un único punto de falla: si se cae el contenedor, se cae todo el módulo.
* Toda la memoria y la CPU son las de una sola máquina (y además compartidas con
  Docker Desktop y los otros contenedores del TPO).
* No prueba réplicas, failover ni distribución de datos.

**No debe presentarse como una topología de alta disponibilidad.**

## 6. Pasos futuros de escala

| Topología | Qué agrega | Cuándo la usaríamos |
|---|---|---|
| Primary + réplicas | Copias del primary. Las lecturas de caché se pueden repartir entre réplicas. Las réplicas pueden estar un poco atrasadas | Si el límite son las lecturas |
| Sentinel | Monitorea el primary y, si se cae, promueve una réplica (failover automático) | Para que la caída de un nodo no tire las sesiones de todos los usuarios |
| Redis Cluster | Reparte las claves en slots entre varios primaries. Suma memoria y capacidad de escritura | Si el límite es la memoria o las escrituras (millones de sesiones) |

En Redis Cluster, las operaciones con varias claves tienen que tener todas las
claves en el mismo slot. Las operaciones del módulo no son multi-clave: cada
`MULTI/EXEC` trabaja sobre una sola clave (una sesión, un contador o un Set),
así que las claves podrían repartirse sin cambiar el diseño. Si en el futuro
hiciera falta una operación atómica sobre varias claves de un mismo usuario, se
forzarían al mismo slot con **hash tags**, como se vio en clase:
`sesion:{S-0001}:perfil` y `sesion:{S-0001}:permisos`.

Excepción: `limpieza.redis` hace `DEL` de varias claves en un comando. En un
Cluster habría que borrarlas de a una, pero es un script de laboratorio, no
parte de la operación normal.

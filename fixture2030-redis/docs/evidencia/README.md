# Evidencia de Ejecución — Hito 7 (Redis)

Registro exigido por RF12, RF13 y RNF10. Este documento cubre el apartado
**Pruebas y evidencia** de la sección 8 del enunciado.

> Corrida real del **02/10/2026, 12:30–12:31 (UTC−3)**, generada de una sola
> vez con `bash tools/generar_evidencia.sh` sobre la notebook descrita en la
> sección 1. Los archivos `.txt` de esta carpeta son la salida sin editar de
> cada paso, numerados en el orden en que se ejecutaron.
> Quien reproduzca el hito en otra máquina debe volver a correr ese script y
> actualizar este resumen: `redis:latest` puede traer otra versión.

---

## 1. Ambiente de prueba

| Dato | Valor | Cómo obtenerlo |
|---|---|---|
| Fecha de ejecución | 2026-10-02, 12:30:25–12:31:05 (UTC−3) | Encabezado de cada `.txt` |
| Integrante que ejecuta | _(completar)_ | — |
| Versión de Redis | **8.10.2** | `INFO server` → `redis_version` |
| Imagen | `redis:latest` (`redis@sha256:6f81e891...150ee`) | `12_recursos.txt` |
| Versión de Docker | 27.5.1 | `docker --version` |
| Sistema operativo | macOS 26.6.2 (Darwin arm64) | — |
| CPU | Apple M1 Pro, 8 núcleos | — |
| RAM total / asignada a Docker | 16 GB / 7,7 GB | Docker Desktop → Settings → Resources |
| Topología | 1 nodo standalone, sin réplicas | — |
| Otros contenedores corriendo | Sí (Cassandra, MongoDB y otros proyectos) | `docker ps` |

## 2. Archivos de evidencia

| Archivo | Qué muestra |
|---|---|
| `00_ambiente.txt` | `docker compose ps` del servicio |
| `01_inicializacion.txt` | `PONG`, versión, `aof_enabled:1`, `maxmemory_human:256.00M`, `maxmemory_policy:volatile-lru` |
| `02_carga_muestra.txt` | Carga de la muestra: `keys=18,expires=17` |
| `03_sesiones.txt` | Crear, recuperar, `HSET` sin renovar, validar y renovar, cerrar, invalidar, sesión inexistente |
| `04_sesiones_expiracion.txt` | La sesión con TTL de 5 s ya no existe a los 7 s (`TTL` = -2) |
| `05_cache.txt` | Hit de P-001, miss de P-002, invalidación con `DEL`, `SET` sin `EX` borra el TTL |
| `06_tasa_hit.txt` | Hits y misses de `cache.redis` (`INFO stats` antes y después) |
| `07_concurrencia.txt` | `INCR`/`SADD` con `EXPIRE` en `MULTI/EXEC`, `ZINCRBY`, Top 3, actividad de sesión, cierre de encuesta |
| `08_prueba_concurrencia.txt` | Clientes en paralelo sin pérdida de actualizaciones |
| `09_medicion.txt` | Tiempo de 20.000 comandos de cada operación principal |
| `10_metricas.txt` | `INFO stats/memory/keyspace`, `SCAN` y TTL observados |
| `11_persistencia.txt` | Las claves sobreviven a `docker compose restart` |
| `12_recursos.txt` | Docker, imagen y recursos asignados |

## 3. TTL observados

| Clave | TTL configurado | TTL observado | Archivo |
|---|---|---|---|
| `sesion:S-0100` recién creada | 1800 | 1800 | `03_sesiones.txt` |
| `sesion:S-0100` tras `EXPIRE 1200` + `HSET` | 1200 (no se renueva) | 1200 | `03_sesiones.txt` |
| `sesion:S-0100` tras el `MULTI/EXEC` de actividad | 1800 | 1800 | `03_sesiones.txt` |
| `sesion:S-0100` tras logout | — | -2 | `03_sesiones.txt` |
| `sesion:S-0199` (5 s) a los 7 s | 5 | -2 | `04_sesiones_expiracion.txt` |
| `cache:partido:P-001` | 300 | 292 | `05_cache.txt` |
| `cache:partido:P-002` recién cargada tras el miss | 300 | 300 | `05_cache.txt` |
| `cache:equipo:ARG` | 3600 | 3592 | `05_cache.txt` |
| `cache:prueba:ttl` tras `SET` sin `EX` | — | -1 | `05_cache.txt` |
| `contador:partido:P-001:visitas` tras `MULTI INCR/EXPIRE` | 172800 | 172800 | `07_concurrencia.txt` |
| `encuesta:partido:P-001:figura` abierta / cerrada | sin TTL / 86400 | -1 / 86400 | `07_concurrencia.txt` |
| `contador:partido:P-999:visitas` tras 100.000 `INCR` | 600 (`INCR` no lo cambia) | 595 | `08_prueba_concurrencia.txt` |
| `sesion:S-0005` tras reiniciar el contenedor | 1800 | 1764 | `11_persistencia.txt` |

## 4. Prueba de concurrencia

**Método:** `bash tools/prueba_concurrencia.sh <clientes> <operaciones>`. Cada
cliente es un proceso `redis-cli` con su propia conexión que manda
`<operaciones>` `INCR` al mismo contador, todos al mismo tiempo.

| Clientes | `INCR` por cliente | Esperado | Obtenido | Resultado |
|---|---|---|---|---|
| 10 | 1.000 | 10.000 | 10.000 | OK |
| 20 | 5.000 | 100.000 | 100.000 | OK |

**Interpretación:** con 20 clientes escribiendo la misma clave al mismo tiempo
no se perdió ninguna actualización, porque `INCR` suma dentro del servidor.
Además el TTL del contador siguió corriendo (595 s): `INCR` no lo borra.

## 5. Medición de operaciones principales

**Método:** `bash tools/medicion.sh 20000`. Para cada operación se arma un
archivo con 20.000 veces el mismo comando y se lo pasa a `redis-cli` **dentro
del contenedor**, tomando la hora en milisegundos antes y después. Es **un
solo cliente** que manda los comandos de a uno y espera cada respuesta. Se
usan claves de prueba `bench:*` con TTL corto que se borran al final.

| Operación del módulo | Comando | Tiempo (20.000 cmds) | Ops/s | Promedio por op. |
|---|---|---|---|---|
| Leer sesión | `HGETALL` | 1.096 ms | 18.248 | 0,055 ms |
| Renovar sesión | `EXPIRE` | 1.738 ms | 11.507 | 0,087 ms |
| Actividad de sesión | `HINCRBY` | 1.770 ms | 11.299 | 0,089 ms |
| Cache hit de partido | `GET` | 1.008 ms | 19.841 | 0,050 ms |
| Escritura de caché | `SET ... EX` | 1.716 ms | 11.655 | 0,086 ms |
| Contador de visitas | `INCR` | 1.691 ms | 11.827 | 0,085 ms |
| Voto en encuesta | `ZINCRBY` | 1.720 ms | 11.627 | 0,086 ms |

**Interpretación:**

* Las lecturas (`GET`, `HGETALL`) tardan unos 0,05 ms por operación y las
  escrituras unos 0,09 ms. Las escrituras son más lentas porque además se
  registran en el AOF.
* El número mide **un cliente esperando cada respuesta**, no la capacidad
  máxima del servidor: con varios clientes en paralelo Redis atiende más
  operaciones por segundo (la prueba de concurrencia hizo 100.000 `INCR` con
  20 clientes en pocos segundos).
* No usamos estos números para afirmar que el nodo soporta los supuestos de
  `patrones_de_acceso.md`; solo muestran que cada operación del módulo es del
  orden de décimas de milisegundo en este equipo.

## 6. Métricas del servidor

Tomadas con `scripts/metricas.redis` al final de la corrida (después de la
medición):

| Métrica | Valor |
|---|---|
| `keyspace_hits` | 40.033 |
| `keyspace_misses` | 11 |
| `expired_keys` | 1 |
| `evicted_keys` | 0 |
| `used_memory_human` | 1,94 MB |
| `maxmemory_human` | 256 MB |
| `maxmemory_policy` | `volatile-lru` |
| `db0` | `keys=19, expires=19` |

Los hits están inflados por la medición (20.000 `GET` + 20.000 `HGETALL`), así
que no sirven como tasa de hit del módulo.

**Tasa de hit de `cache.redis`** (`06_tasa_hit.txt`, restando `INFO stats`
antes y después del script): 8 hits y 3 misses → 8 / 11 = **72,7 %**. Este
número solo refleja `cache.redis`, que provoca misses a propósito para mostrar
el flujo; además `INFO` cuenta también los `TTL`. **No es una predicción de la
tasa de hit en producción.**

## 7. Limitaciones del laboratorio

* Un solo nodo en una notebook, compartiendo CPU y memoria con otros
  contenedores. Los números no representan un servidor dedicado ni un cluster.
* La medición corre dentro del mismo contenedor que Redis: no hay red de por
  medio. En producción la latencia de red se suma a estos valores.
* Cada prueba repite un comando sobre una sola clave; no reproduce la mezcla
  real de tráfico de la plataforma.
* No se probó llegar al límite de 256 MB, por eso `evicted_keys` es 0. El
  comportamiento ante presión de memoria está analizado en
  `memoria_y_escalabilidad.md`, no medido.
* Los scripts simulan la consulta a MongoDB/Neo4j escribiendo el valor a mano:
  no hay integración física con esos módulos (el enunciado no la pide).

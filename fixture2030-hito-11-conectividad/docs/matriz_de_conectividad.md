# Matriz de conectividad (RF16, RNF9, RNF17, RNF18)

> Revisión del 19/10/2026: los archivos de evidencia del 17/10 son históricos.
> La implementación actual usa drivers oficiales, valida las respuestas negativas
> y corrige el resumen y el modo estricto. No se deben atribuir los resultados
> anteriores al código corregido. Ver [walkthrough de las correcciones](walkthrough_correcciones.md)
> y [evidencia nueva](evidencia/revision_2026-10-19/README.md).


Grupo 4 — Ingeniería de Datos II — Fixture 2030

La matriz la genera `scripts/evaluar_conectividad.sh` al final de cada corrida
(consola, `--json` y `--markdown`). Esta página resume las corridas de la
evidencia. El detalle de cada prueba (instante, capa, destino, duración y
diagnóstico) está en [`evidencia/matriz_completa.md`](evidencia/matriz_completa.md)
y en los `.json`.

## 1. Estados

**Por prueba**

| Estado | Significado |
|---|---|
| OK | Esa prueba concreta funcionó, en ese momento y desde ese origen. No garantiza rendimiento ni disponibilidad permanente |
| WARN | Funcionó con una observación que hay que leer (dato de prueba ausente, lectura más lenta que `UMBRAL_LENTO_MS`, diagnóstico de la API que informa una fuente afectada) |
| FAIL | Se intentó y falló. Siempre incluye **hipótesis** y **siguiente paso** (RNF10) |
| SKIP | No se ejecutó: falta una herramienta o configuración, o falló una capa previa. **No es "producto caído"** |

**Por producto (RNF9)**

| Estado | Regla |
|---|---|
| disponible | Todas las capas ejecutadas, hasta la lectura, terminaron en OK (o en WARN sin degradación) |
| degradado | La lectura nativa funciona, pero una sonda o prueba secundaria falla, la API informa una fuente afectada o la lectura supera `UMBRAL_LENTO_MS` |
| no disponible | Falló una capa de la cadena (resolución → lectura) |
| desconocido | Se ejecutaron capas sin falla, pero no se llegó a la lectura (por ejemplo `--modo tcp`): no alcanza para declararlo disponible |
| no probado | Todas las capas de la cadena quedaron en SKIP o no se ejecutaron (por ejemplo `--modo api`, que solo prueba la columna API) |
| no configurado | Faltan variables imprescindibles: no se intentó la conexión |

Ningún producto se marca disponible por suposición: el estado inicial es
"no probado" y solo cambia con una prueba ejecutada.

## 2. Matriz principal — modo completo desde la notebook

| Campo | Valor |
|---|---|
| Fecha | 2026-10-17 00:33:10 UTC (duración 8,5 s) |
| Commit | `db0f5fc` (rama `hito10`) + cambios del Hito 11 sin commitear al momento de la corrida |
| Entorno / origen | Notebook Windows 11, Git Bash, Python 3.12.10; `127.0.0.1` = puertos publicados por Docker Desktop 29.7.2 |
| Drivers | pymongo 4.19.0, neo4j 6.4.1, cassandra-driver 3.30.1, redis 8.1.0, intersystems-irispython 5.4.1 |
| API | `http://127.0.0.1:8000`, versión 1.1.0 |
| Resultado | 97 pruebas: 95 OK, 1 WARN, 0 FAIL, 1 SKIP (la sonda opcional de expiración de Redis) |
| Evidencia | [`resultados_completo.txt`](evidencia/resultados_completo.txt), [`resultados_completo.json`](evidencia/resultados_completo.json), [`matriz_completa.md`](evidencia/matriz_completa.md) |

| Producto | Estado | Cfg | DNS | TCP | Prot | AuthN | AuthZ | Ctx | Lect | Sondas | API | Lectura (ms) | Diagnóstico |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MongoDB | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 3,5 | Todas las capas OK |
| Neo4j | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 4/4 | OK | 5,9 | Todas las capas OK; el portal HTTP también responde |
| Cassandra | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 4/4 | OK | 77,2 | Todas las capas OK; 4 particiones por lectura |
| Redis | **disponible** | OK | OK | OK | OK | OK | OK | OK | WARN | 2/2 | OK | 1,2 | `sesion:S-0001` ausente (TTL vencido): ausencia válida, no caída |
| InfluxDB | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 34,2 | Todas las capas OK; 1800 puntos en 15 min |
| IRIS | **disponible** | OK | OK | OK | OK | OK | OK | OK | OK | 3/3 | OK | 3,3 | Todas las capas OK; el portal HTTP también responde |

Limitaciones de esta matriz: un solo nodo por producto, credenciales de
laboratorio, datos de muestra y una corrida puntual. Las latencias son de una
lectura mínima y no dicen nada sobre carga (Hito 12).

## 3. Otras corridas de la evidencia

| Corrida (2026-10-17 UTC) | Origen | Resultado por producto | Evidencia |
|---|---|---|---|
| Modo TCP, 00:32 | notebook | Los seis **desconocido**: configuración, DNS y TCP en OK; no alcanza para declararlos disponibles | `resultados_tcp.txt` |
| Modo nativo (con la sonda de expiración de Redis), 00:32 | notebook | Los seis **disponible**; 78 pruebas, 77 OK, 1 WARN | `resultados_clientes.txt` |
| Modo nativo, 00:32 | contenedor en `tpo_fixture2030_default` | Los seis **disponible** (nombres de servicio); contenedor en SKIP (sin daemon) | `resultados_red_docker.txt` |
| Modo TCP con `127.0.0.1`, 00:32 | contenedor | MongoDB y Redis **no disponible** (TCP refused en 0 ms): configuración de la notebook usada en el entorno equivocado | `resultados_red_docker.txt` |
| Modo API, 00:33 | notebook | Columna API OK para los seis; capas nativas no probadas en ese modo | `resultados_api.txt` |
| Fallo controlado, 00:33 | notebook | MongoDB **no disponible** (TCP refused) → **disponible** tras `docker start` | `fallo_controlado_mongodb.txt` |
| Escenarios A1–A6, 00:33 | notebook | Cada producto **no disponible** en la capa del error → los seis **disponible** con la configuración corregida (A7) | `escenarios_configuracion.txt` |
| API con configuración errónea (B1), 00:34 | notebook → API temporal en 8002 | Columna API FAIL para los seis: 503/504 con la dependencia identificada; readiness 503 | `escenarios_configuracion.txt` |
| API con timeout de 1 ms (B2), 00:34 | notebook → API temporal en 8003 | Solo InfluxDB FAIL (504); el resto respondió dentro de 1 ms | `escenarios_configuracion.txt` |

## 4. Cambio de estado documentado (RF20)

| Producto | Antes | Cambio | Después | Tiempo |
|---|---|---|---|---|
| MongoDB | disponible (00:33:19) | `docker stop` → **no disponible**: TCP *connection refused* tras 2057 ms; API 503 en 2,06 s | `docker start` → **disponible** (00:33:46) | protocolo disponible 2375 ms después del `start` |
| Neo4j | disponible | `NEO4J_DATABASE=noexiste` → **no disponible** en Ctx (`DatabaseNotFound`) | configuración original → **disponible** | inmediato |
| Cassandra | disponible | `CASSANDRA_KEYSPACE=fixture2030_inexistente` → **no disponible** en Ctx | **disponible** | inmediato |
| Redis | disponible | `REDIS_PORT=6380` → **no disponible** en TCP (refused tras 2042 ms) | **disponible** | inmediato |
| InfluxDB | disponible | `INFLUX_DATABASE=…_inexistente` → **no disponible** en Ctx; `TIMEOUT_OPERACION_S=0.001` → **no disponible** en lectura (timeout) | **disponible** | inmediato |
| IRIS | disponible | `IRIS_NAMESPACE=NOEXISTE` → AuthN OK (verificada en `USER`) y **Ctx FAIL** (`Exists = 0`) | **disponible** | inmediato |

Un error interno del evaluador se registra como FAIL, conserva hipótesis y siguiente paso y deja el producto en **desconocido**. `--estricto` devuelve 1. Las pruebas de API se asocian a sus dependencias antes de calcular el estado, sin afectar a las fuentes sanas.

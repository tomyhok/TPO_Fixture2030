# Evidencia del Dashboard de Grafana — Hito 13

Evidencia **observada** del dashboard **Fixture Mundial 2030 — Observabilidad y Monitoreo NoSQL (Hito 13)** (`uid: fixture2030-war-room`, definido en [`../../grafana/dashboards/fixture2030_war_room.json`](../../grafana/dashboards/fixture2030_war_room.json)) durante la corrida del **2026-11-23**, que incluyó tráfico sostenido y la prueba de falla controlada sobre Redis ([`../prueba_de_falla.md`](../prueba_de_falla.md)).

## 1. Línea de tiempo de la corrida

Las capturas y los CSV de Grafana están en **hora local (UTC−3)**; los exports de Prometheus y `prueba_de_falla.*`, en **UTC**.

| Evento | UTC | Hora local |
|---|---|---|
| Inicio del tráfico de lectura (GET a 6 rutas, una por base) | 20:38:05 | 17:38:05 |
| Inicio de la prueba controlada (fase 1) | 20:44:46 | 17:44:46 |
| `docker stop fixture2030-redis` → `fixture_db_up{db="redis"} = 0` | 20:46:00 | 17:46:00 |
| `docker start fixture2030-redis` → `fixture_db_up{db="redis"} = 1` | 20:47:30 | 17:47:30 |
| Fin de la prueba (fase 3) | 20:47:40 | 17:47:40 |
| Sin alertas activas en Prometheus | 20:48:58 | 17:48:58 |
| Fin del tráfico (caída final a 0 en los paneles de throughput) | 20:58:12 | 17:58:12 |

## 2. Archivos

| Archivo | Tipo | Origen |
|---|---|---|
| [`capturas/2026-11-23_fila1_disponibilidad.jpg`](capturas/2026-11-23_fila1_disponibilidad.jpg) | Captura | Fila 1: `up` y `fixture_db_up` |
| [`capturas/2026-11-23_fila2_latencia_throughput_api.jpg`](capturas/2026-11-23_fila2_latencia_throughput_api.jpg) | Captura | Fila 2: latencia p95/promedio y req/s por ruta |
| [`capturas/2026-11-23_fila3_latencia_bases_errores.jpg`](capturas/2026-11-23_fila3_latencia_bases_errores.jpg) | Captura | Fila 3: latencia por base y errores `increase[5m]` |
| [`capturas/2026-11-23_fila4_throughput_bases_host.jpg`](capturas/2026-11-23_fila4_throughput_bases_host.jpg) | Captura | Fila 4: ops/s por base y CPU/RAM del host |
| [`grafana_csv/01..08_*.csv`](grafana_csv/) | Datos | Grafana → *Inspect → Data* con **Series joined by time** y sin formato (una columna por serie, timestamp epoch en ms) |
| [`datos_paneles_20261123T203800Z.json`](datos_paneles_20261123T203800Z.json) / [`.csv`](datos_paneles_20261123T203800Z.csv) | Datos | Prometheus `/api/v1/query_range`, 20:38–20:49 UTC, paso 15s, las **63 series de los 8 paneles** con su PromQL |
| [`vista_dashboard_war_room.svg`](vista_dashboard_war_room.svg) | **Maqueta** | Dibujada a mano antes de la corrida; **no es una captura** ni contiene datos observados |

El export de Prometheus se regenera con:

```bash
python scripts/exportar_datos_dashboard.py --desde 2026-11-23T20:38:00Z --hasta 2026-11-23T20:49:00Z
```

(Prometheus conserva los datos 7 días: `--storage.tsdb.retention.time=7d`.) Los CSV de Grafana y el export de Prometheus coinciden punto a punto (por ejemplo, Redis en `0` entre 20:46:00 y 20:47:15 UTC en ambos).

## 3. Qué muestra cada captura

Las capturas se tomaron **después de la recuperación** (~17:57 local) con rango *Last 15 minutes*, de modo que los paneles de series temporales muestran el **antes, durante y después** de la falla.

- **Fila 1 — Disponibilidad.** Los paneles *stat* muestran el **último valor**, por eso se ve todo en verde: es el estado tras la recuperación. La caída de Redis a `0` está registrada en [`grafana_csv/02_fixture_db_up.csv`](grafana_csv/02_fixture_db_up.csv) y en el export de Prometheus; la alerta `BaseDatosNoSQLNoDisponible` en `firing` quedó registrada en [`../prueba_de_falla.json`](../prueba_de_falla.json) (fase 2).
- **Fila 2 — API.** El p95 de `/sesiones/{id_sesion}` y `/health/dependencias` sube a ~2,4 s durante la falla (timeout de conexión a Redis de 2 s); el resto de las rutas se mantiene bajo el SLA de 100 ms (p95 de `/equipos` 7,8 ms promedio, 13,1 ms máximo). En throughput aparece `/sesiones [HTTP 504]` solo durante la falla.
- **Fila 3 — Bases y errores.** `op redis:sesion.hmget_ttl` sube a ~2 s; MongoDB (`~2,4 ms`), Neo4j (`~4,2 ms`) e IRIS (`~3 ms`) no cambian. Los errores `DEPENDENCIA_TIMEOUT` en `/sesiones` llegan a 38,9 en la ventana de 5 min y vuelven a 0 cuando la falla sale de la ventana.
- **Fila 4 — Throughput por base e infraestructura.** CPU del host ~4 % y RAM ~68 % estables: la falla no es de infraestructura.

## 4. Interpretación — puntos que no deben leerse mal

1. **Redis respondió `504` y no `503`.** En Windows/Docker Desktop, la conexión a un contenedor detenido no se rechaza al instante: espera hasta `timeout_conexion_s = 2 s` y la API la clasifica como `DEPENDENCIA_TIMEOUT` (504). Por eso la verificación "ruta de redis responde 503" figura como **No** en [`../prueba_de_falla.md`](../prueba_de_falla.md). No se corrigió a mano.
2. **La baja de throughput en *todas* las rutas (≈2,1 → 0,42 req/s) la causa el generador de tráfico, no la API.** El generador envía las requests **en secuencia**; cada request a `/sesiones` quedaba esperando ~2,4 s, lo que frenaba el ciclo completo. La latencia del lado del servidor de las demás rutas no cambió (fila 2 y fila 3), lo que muestra que la falla quedó **aislada** en Redis.
3. **La latencia medida por el script de la prueba (~2 s en `/equipos`) es del cliente.** Del lado del servidor, `/equipos` se mantuvo en 5–11 ms (p95). La diferencia de ~2 s coincide en `/sesiones` (4 s en el cliente contra 2,4 s en el servidor); la causa probable es la resolución de `localhost` en Windows (no verificada). Ese contraste es justamente cómo se distingue un problema de API, de base o de cliente.
4. **`undefined` en los CSV de Grafana** indica que la serie todavía no existía (los contadores de error se crean con el primer error), no un valor 0.
5. **La caída final a 0 req/s (~17:58 local)** es el fin programado del generador de tráfico, no una falla.

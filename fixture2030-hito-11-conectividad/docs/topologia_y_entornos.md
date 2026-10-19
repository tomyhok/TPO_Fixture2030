# Topología y entornos (RF2, RNF3)

Grupo 4 — Ingeniería de Datos II — Fixture 2030

## 1. Dónde corre cada cosa

```
 NOTEBOOK (Windows 11)                         DOCKER DESKTOP (VM Linux)
 ┌──────────────────────────────┐             ┌──────────────────────────────────────────────────────┐
 │ API Hito 10 (uvicorn)        │  127.0.0.1  │  puertos publicados        red tpo_fixture2030_default │
 │  127.0.0.1:8000              │ ──────────▶ │  0.0.0.0:27017 ─────────▶ fixture2030-mongodb   :27017 │
 │                              │             │  0.0.0.0:7687/7474 ─────▶ fixture2030-neo4j     :7687  │
 │ Diagnóstico Hito 11          │             │  0.0.0.0:9042 ──────────▶ fixture2030-cassandra :9042  │
 │  (mismo origen que la API)   │ ──────────▶ │  0.0.0.0:6379 ──────────▶ fixture2030-redis     :6379  │
 │                              │             │  0.0.0.0:8181 ──────────▶ fixture2030-influxdb  :8181  │
 │ curl / Postman / navegador   │             │  0.0.0.0:1972/52773 ────▶ fixture2030-iris      :1972  │
 └──────────────────────────────┘             │                                                      │
                                              │  contenedor efímero del diagnóstico (opcional) ──▶   │
                                              │  mongodb:27017, neo4j:7687, ... (nombre de servicio) │
                                              │                                                      │
                                              │  API en contenedor (opcional, Hito 10): 8000 interno │
                                              │  publicado en 127.0.0.1:8001                         │
                                              └──────────────────────────────────────────────────────┘
```

| Componente | Dónde se ejecuta en la evaluación | Cómo llega a las bases |
|---|---|---|
| Bases (6) | Contenedores del `docker-compose.yml` raíz, red `tpo_fixture2030_default` | — |
| API del Hito 10 | **Proceso en la notebook** (modo principal), `127.0.0.1:8000` | Puertos publicados en `127.0.0.1` |
| Diagnóstico del Hito 11 | **Proceso en la notebook**, mismo origen que la API | Igual que la API: mismas variables y mismo `.env` |
| Diagnóstico desde la red Docker | Contenedor efímero con la imagen de la API (`scripts/evaluar_desde_red_docker.sh`) | Nombre de servicio y puerto **interno** |
| CLI oficiales | Dentro del contenedor de cada producto (`scripts/clientes_en_contenedor.sh`) | `localhost` del contenedor = el propio producto |
| API en contenedor | Opcional (`docker-compose.api.yml` del Hito 10); **no estaba levantada** en esta evaluación | Nombre de servicio |

Se evaluó **desde el origen real de la API** (la notebook). Las otras dos
ubicaciones se usan para contrastar resultados, porque responden a otra pregunta.

## 2. Puertos publicados e internos

Evidencia: [`evidencia/00_entorno_y_topologia.txt`](evidencia/00_entorno_y_topologia.txt).

| Servicio Compose | Contenedor | IP interna observada | Puerto interno | Publicado en la notebook | Protocolo | Lo usa la API |
|---|---|---|---|---|---|---|
| `mongodb` | fixture2030-mongodb | 172.19.0.7 | 27017 | `0.0.0.0:27017` | MongoDB Wire | sí |
| `neo4j` | fixture2030-neo4j | 172.19.0.5 | 7687 / 7474 | `0.0.0.0:7687` / `0.0.0.0:7474` | Bolt / HTTP | Bolt sí, HTTP no |
| `cassandra` | fixture2030-cassandra | 172.19.0.3 | 9042 | `0.0.0.0:9042` | CQL | sí |
| `redis` | fixture2030-redis | 172.19.0.6 | 6379 | `0.0.0.0:6379` | RESP | sí |
| `influxdb` | fixture2030-influxdb | 172.19.0.4 | 8181 | `0.0.0.0:8181` | HTTP | sí |
| `iris` | fixture2030-iris | 172.19.0.2 | 1972 / 52773 | `0.0.0.0:1972` / `0.0.0.0:52773` | Superserver / HTTP | Superserver sí, portal no |

Las IP internas las asigna Docker y pueden cambiar al recrear la red: **nunca se
configuran**. Dentro de la red se usa el nombre del servicio. Desde la notebook
se usa `127.0.0.1` y el puerto publicado. En este compose el puerto publicado
coincide con el interno. Si se cambiara el mapeo (`"27018:27017"`), la notebook
usaría 27018 y los contenedores seguirían usando 27017.

## 3. Lo que cambia según el origen (medido)

| Prueba | Desde la notebook | Desde un contenedor en la red | Evidencia |
|---|---|---|---|
| `MONGO_HOST=mongodb` | **FAIL resolución**: `getaddrinfo failed` (2,7 s) | OK: resuelve a la IP interna | `escenarios_configuracion.txt` A1, `resultados_red_docker.txt` |
| `MONGO_HOST=127.0.0.1` | OK (puerto publicado) | **FAIL TCP**: *connection refused*, porque `127.0.0.1` es el propio contenedor | `resultados_red_docker.txt` (2.ª parte) |
| Puerto cerrado en `127.0.0.1` | *connection refused* tras **~2,0 s** | *connection refused* en **0–10 ms** | `resultados_clientes.txt` (sonda Redis), `resultados_red_docker.txt` |
| `localhost` | Resuelve primero a `::1` (IPv6). Con un puerto solo IPv4, cada intento fallido duplica la espera (medido en el Hito 10) | — | `conectividad_y_configuracion.md` del Hito 10 |
| Seis productos, modo nativo | 6 disponibles | 6 disponibles | `resultados_clientes.txt`, `resultados_red_docker.txt` |

**Windows y los 2 segundos.** En Windows, un `connect()` a un puerto cerrado de
`127.0.0.1` no falla en el acto: el stack TCP reintenta el SYN después del RST y
devuelve `WSAECONNREFUSED` a los ~2 s (medido: 2052 ms con 5 s de límite y
`TimeoutError` a los 1511 ms con 1,5 s de límite). Consecuencias:

* El diagnóstico usa `TCP_TIMEOUT_S=3` para poder ver *connection refused* y no confundirlo con un timeout.
* La API usa `TIMEOUT_CONEXION_S=2`. Por eso Redis detenido aparece como **504 DEPENDENCIA_TIMEOUT** (Hito 10, `09_dependencia_caida.txt`) y no como 503. MongoDB detenido aparece como 503 a los ~2,0–2,5 s, porque su selección de servidor convierte el rechazo en `ServerSelectionTimeoutError`.
* Dentro de la red Docker (Linux) el rechazo es inmediato: la misma caída se clasificaría como "no disponible" sin esperar.

## 4. Variables por entorno

Fuente única: el `.env` del Hito 10 (no versionado), más
`config/conectividad.env` (opcional) y las variables de entorno. El ejemplo
completo está en [`../config/configuracion-ejemplo.env`](../config/configuracion-ejemplo.env).

| Variable | Notebook (valor de ejemplo) | Red Docker | Secreto |
|---|---|---|---|
| `API_URL` | `http://127.0.0.1:8000` | `http://api:8000` (si la API corre en el contenedor) | no |
| `MONGO_HOST` / `MONGO_PORT` | `127.0.0.1` / `27017` | `mongodb` / `27017` | no |
| `MONGO_USER` / `MONGO_PASSWORD` | `admin` / `<completar>` | igual | **contraseña sí** |
| `MONGO_DATABASE` | `fixture2030` | igual | no |
| `NEO4J_URI` / `NEO4J_HTTP_URL` | `bolt://127.0.0.1:7687` / `http://127.0.0.1:7474` | `bolt://neo4j:7687` / `http://neo4j:7474` | no |
| `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | `neo4j` / `<completar>` / `neo4j` | igual | **contraseña sí** |
| `CASSANDRA_HOSTS` / `CASSANDRA_PORT` / `CASSANDRA_KEYSPACE` / `CASSANDRA_DC` | `127.0.0.1` / `9042` / `fixture2030` / `datacenter1` | `cassandra` / … | no |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD` | `127.0.0.1` / `6379` / `0` / vacío | `redis` / … | contraseña sí (vacía en el laboratorio) |
| `INFLUX_URL` / `INFLUX_DATABASE` | `http://127.0.0.1:8181` / `fixture2030` | `http://influxdb:8181` / … | no |
| `INFLUX_TOKEN` / `INFLUX_TOKEN_FILE` | vacío / `../fixture2030-influxDB/.influxdb3-token` | vacío / `/run/secrets/influx_token` (montado de solo lectura) | **token sí** |
| `IRIS_HOST` / `IRIS_PORT` / `IRIS_PORTAL_URL` | `127.0.0.1` / `1972` / `http://127.0.0.1:52773/csp/sys/UtilHome.csp` | `iris` / `1972` / `http://iris:52773/...` | no |
| `IRIS_NAMESPACE` / `IRIS_USER` / `IRIS_PASSWORD` | `USER` / `fixture_api` / `<completar>` | igual | **contraseña sí** |
| `TCP_TIMEOUT_S` / `TIMEOUT_CONEXION_S` / `TIMEOUT_OPERACION_S` / `API_TIMEOUT_S` | `3` / `2` / `5` / `15` | igual | no |

`scripts/evaluar_desde_red_docker.sh` aplica la columna "Red Docker". Pasa el
`.env` con `--env-file`, así las contraseñas no aparecen en los argumentos del
proceso, y monta el token de solo lectura.

## 5. Cómo se verifica que se prueba desde el origen correcto

Cada corrida imprime y guarda en su JSON el campo `origen`:

* `notebook Windows 11 (Git Bash); 127.0.0.1 = puertos publicados por Docker`
* `contenedor Docker (Linux); localhost = el propio contenedor` (si existe `/.dockerenv`)

Desde un contenedor, el diagnóstico no consulta el daemon de Docker: la capa
`contenedor` queda en SKIP con el motivo.

# Hito 10 — Conectividad, Configuración y Seguridad

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Conectividad** y **Seguridad** de la
sección 8 del enunciado y la sección 5.13 (RF16, RNF6–RNF10).

---

## 1. Dónde se ejecuta cada componente

| Componente | Modo notebook (principal) | Modo contenedor (opcional) |
|---|---|---|
| Bases (6) | Contenedores del `docker-compose.yml` raíz | Iguales |
| API | Proceso Python 3.12 en la notebook (`scripts/iniciar_api.*`), puerto **8000** | Contenedor `fixture2030-api` (`docker-compose.api.yml`), puerto **8001** |
| Pruebas | pytest en la notebook | pytest en la notebook (contra la API de la notebook) |
| Scripts de datos | Bash en la notebook + `docker exec` | Iguales |

## 2. Hosts y puertos

Desde la notebook las bases se alcanzan por los puertos publicados en
`127.0.0.1`. Dentro de la red de Docker se alcanzan por el **nombre del
servicio** y el puerto interno. Por eso el compose de la API reemplaza los
hosts con variables de entorno, sin tocar el código.

| Fuente | Variable(s) | Desde la notebook | Desde un contenedor |
|---|---|---|---|
| MongoDB | `MONGO_HOST`, `MONGO_PORT`, `MONGO_DATABASE`, `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_AUTH_DB` | `127.0.0.1:27017`, db `fixture2030` | `mongodb:27017` |
| Neo4j | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | `bolt://127.0.0.1:7687`, db `neo4j` | `bolt://neo4j:7687` |
| Cassandra | `CASSANDRA_HOSTS`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE`, `CASSANDRA_DC` | `127.0.0.1:9042`, keyspace `fixture2030` | `cassandra:9042` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB` | `127.0.0.1:6379`, db 0 | `redis:6379` |
| InfluxDB 3 | `INFLUX_URL`, `INFLUX_DATABASE`, `INFLUX_TOKEN` o `INFLUX_TOKEN_FILE` | `http://127.0.0.1:8181`, database `fixture2030` | `http://influxdb:8181` |
| IRIS | `IRIS_HOST`, `IRIS_PORT`, `IRIS_NAMESPACE`, `IRIS_USER`, `IRIS_PASSWORD` | `127.0.0.1:1972`, namespace `USER` | `iris:1972` |
| API | `API_HOST`, `API_PORT` | `127.0.0.1:8000` | `0.0.0.0:8000` en el contenedor, publicado en `127.0.0.1:8001` |

Se usa `127.0.0.1` y no `localhost`: en Windows `localhost` resuelve primero a
IPv6 (`::1`) y después a IPv4, y con una base caída el cliente espera el
timeout dos veces (se midió 4 s en lugar de 2 s).

## 3. Configuración sin secretos en el repositorio (RF16, RNF6, RNF7)

* `app/config/settings.py` define **qué** variables existen y sus valores por
  defecto **no secretos**. Las contraseñas tienen por defecto una cadena vacía.
* `.env.example` (versionado) lista todas las variables, con `<completar>` en
  las contraseñas.
* `.env` (local, **excluido** por `.gitignore`) tiene los valores reales.
* El token de InfluxDB no se copia. Si `INFLUX_TOKEN` está vacío, la API lee
  `fixture2030-influxDB/.influxdb3-token`, que genera el Hito 8 y que ya está
  excluido del repositorio. En modo contenedor se monta de solo lectura en
  `/run/secrets/influx_token`.
* IRIS: la API **no** usa `_SYSTEM`. `scripts/preparar_datos.sh` crea el
  usuario `IRIS_USER` con la contraseña de `.env` y el rol `FixtureAPI`, que
  solo tiene `%DB_USER` (base `USER`) y `%Native_ClassExecution:U`. La
  contraseña viaja por stdin a la sesión de IRIS: no queda en argumentos de
  procesos ni en logs.
* Las contraseñas se modelan como `SecretStr`: si se imprimen los settings,
  se ven `**********`.

## 4. Timeouts (RNF8, RNF9)

| Variable | Valor | Uso |
|---|---|---|
| `TIMEOUT_CONEXION_S` | 2 s | Abrir la conexión con la fuente |
| `TIMEOUT_OPERACION_S` | 5 s | Cada consulta o escritura |

| Fuente | Cómo se aplica |
|---|---|
| MongoDB | `serverSelectionTimeoutMS`, `connectTimeoutMS` = conexión. `socketTimeoutMS` = operación |
| Neo4j | `connection_timeout` = conexión. `Query(timeout=...)` = operación. Auto-commit sin reintentos automáticos |
| Cassandra | `connect_timeout`, `control_connection_timeout` = conexión. `ExecutionProfile.request_timeout` = operación |
| Redis | `socket_connect_timeout` y `socket_timeout`. Reintentos del cliente desactivados (`Retry(NoBackoff(), 0)`) |
| InfluxDB | `httpx.Timeout(operación, connect=conexión)` |
| IRIS | `timeout` de `iris.connect` + límite de espera del hilo (conexión + operación), porque el cliente no tiene timeout por operación |

La prueba `test_fuente_lenta_corta_por_timeout` usa un servidor que acepta
conexiones y nunca responde: la API corta en el tiempo configurado y responde
503 o 504. Nunca queda esperando indefinidamente.

## 5. Procedimiento de conexión y prueba

1. Levantar las bases desde la raíz del repositorio: `docker compose up -d`.
2. Configurar: `cp .env.example .env` y completar las contraseñas.
3. Preparar los datos: `bash scripts/preparar_datos.sh`.
4. Verificar cada dependencia: `bash scripts/verificar_conectividad.sh`.
   Muestra el estado de los contenedores y hace ping a cada fuente con los
   mismos adaptadores que usa la API. Termina con código ≠ 0 si alguna falla.
5. Iniciar la API: `bash scripts/iniciar_api.sh` (o `.ps1`).
6. Verificar desde la API: `GET http://127.0.0.1:8000/health`.
7. Detener: `Ctrl+C` en la API. Las bases se detienen con `docker compose stop`
   o `docker compose down`, **sin** `-v` para no borrar volúmenes. Los datos
   de Cassandra, Redis, InfluxDB e IRIS viven en `~/docker/data/` y no se
   borran con `down`.

Modo contenedor (opcional), desde la raíz:

```bash
docker compose -f docker-compose.yml -f fixture2030-hito-10-api-integrada/docker-compose.api.yml up -d --build api
curl http://127.0.0.1:8001/health
docker compose -f docker-compose.yml -f fixture2030-hito-10-api-integrada/docker-compose.api.yml rm -sf api   # quitarlo
```

## 6. Logs (RNF10) y seguridad

Formato de cada línea (UTC):

```
2026-10-15T18:28:47Z INFO [fixture2030.adaptador] request_id=<id> dependencia=cassandra operacion=comentarios.batch_insert resultado=ok duracion_ms=13.6
2026-10-15T18:28:47Z INFO [fixture2030.acceso] request_id=<id> metodo=POST ruta=/partidos/P-001/comentarios estado=201 duracion_ms=25.2
```

| Se registra | No se registra |
|---|---|
| Método, ruta (sin query string), estado, duración | Cuerpos de request y de respuesta |
| `request_id` en todas las líneas de la request | Credenciales, tokens, URIs de conexión |
| Dependencia, operación lógica, resultado (`ok`, `DEPENDENCIA_TIMEOUT:TimeoutError`, ...) y duración | Consultas completas y parámetros |
| Detalle interno de IRIS ante un rechazo de negocio (`%Status`) | Datos de sesión |
| Traza completa ante un error 500, solo en el log | Hosts y puertos de los drivers (los loggers de los drivers quedan en WARNING) |

El access log propio de uvicorn está desactivado (`--no-access-log`) porque
duplicaría la línea de acceso e incluiría la query string. Los logs se guardan
en `logs/api.log`, que está excluido del repositorio. La evidencia
`evidencia/10_logs_correlacion.txt` muestra que no hay coincidencias de
`password|token|secret` en el log.

**Archivos excluidos del repositorio** (`.gitignore` del hito y de la raíz):
`.env`, `.env.*` (salvo `.env.example`), `.venv/`, `logs/`, `__pycache__/`,
`.pytest_cache/`, `fixture2030-influxDB/.influxdb3-token`, `*.lp`.

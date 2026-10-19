# Hito 11 — Evaluación de la conectividad a los productos del Fixture 2030

Grupo 4 — Ingeniería de Datos II

Procedimiento reproducible para evaluar, **capa por capa**, la conectividad entre
la API integrada del Hito 10 y sus seis productos NoSQL (MongoDB, Neo4j,
Cassandra, Redis, InfluxDB 3 e InterSystems IRIS). El procedimiento permite
identificar en qué capa falla una dependencia, registrar evidencia sin secretos
y comprobar cómo se comporta la API cuando un producto está caído, rechaza la
conexión, responde lento, no autentica o tiene un contexto inexistente.

```
Configuración → Resolución → TCP → Protocolo → Autenticación → Autorización → Contexto → Lectura mínima → Endpoint de la API
```

> **Qué significa OK.** Que una prueba concreta funcionó en ese momento y desde
> ese origen. No es una garantía de rendimiento, escalabilidad ni
> disponibilidad permanente (eso es el Hito 12). **SKIP** significa "prueba no
> ejecutada por falta de herramienta, de configuración o porque falló una capa
> previa"; **no** significa "producto caído".

## Resultado de la última evaluación

Corrida del 2026-10-17 00:33 UTC (modo completo, 97 pruebas: 95 OK, 1 WARN, 0 FAIL, 1 SKIP) desde la notebook (Windows 11, Git Bash), commit
base `db0f5fc` con los cambios de este hito. Detalle en
[`docs/matriz_de_conectividad.md`](docs/matriz_de_conectividad.md).

| Producto | Estado | Capas (Cfg→Lectura) | Sondas | API | Lectura (ms) |
|---|---|---|---|---|---|
| MongoDB | **disponible** | 8/8 OK | 3/3 | OK | 3,5 |
| Neo4j | **disponible** | 8/8 OK | 4/4 | OK | 5,9 |
| Cassandra | **disponible** | 8/8 OK | 4/4 | OK | 77,2 |
| Redis | **disponible** | 7 OK + lectura WARN* | 2/2 | OK | 1,2 |
| InfluxDB | **disponible** | 8/8 OK | 3/3 | OK | 34,2 |
| IRIS | **disponible** | 8/8 OK | 3/3 | OK | 3,3 |

\* La sesión de muestra `sesion:S-0001` ya había vencido (TTL de 30 min del
Hito 7). Redis respondió normalmente: es una **clave ausente**, no "Redis caído".

Hallazgos que llevaron a cambios en la API (detalle en
[`docs/diagnostico_de_fallas.md`](docs/diagnostico_de_fallas.md)):

1. Con `NEO4J_DATABASE` inexistente la API respondía **500**: ahora responde 503 e identifica la dependencia.
2. Con `MONGO_DATABASE` inexistente la API respondía **404 "no existe la selección"**, una ausencia falsa: ahora responde 503.
3. En Windows, un puerto cerrado en `127.0.0.1` tarda **~2 s** en devolver *connection refused*. Con `TIMEOUT_CONEXION_S=2`, algunas caídas se informan como timeout (504). Dentro de Docker (Linux) el rechazo tarda menos de 10 ms.
4. IRIS responde **"Access Denied"** igual para una credencial inválida que para un namespace inexistente. Además, su cliente se cuelga si apunta al puerto del portal. El diagnóstico separa ambos casos y pone un límite de espera propio.

## Requisitos

* Docker Desktop con los contenedores del [`docker-compose.yml`](../docker-compose.yml) de la raíz, levantados y con los datos preparados por el Hito 10 (`bash ../fixture2030-hito-10-api-integrada/scripts/preparar_datos.sh`).
* El `.env` de la API del Hito 10 (copiado de `.env.example`). El diagnóstico lo reutiliza: **no hay que duplicar credenciales**.
* Python 3.11+ con los drivers. Por defecto se usa el entorno virtual del Hito 10 (`../fixture2030-hito-10-api-integrada/.venv`), que tiene exactamente las mismas versiones que la API. Otra opción: `PYTHON=/ruta/python` con [`requirements.txt`](requirements.txt) instalado.
* Git Bash (o cualquier bash) para los scripts `.sh`. Desde PowerShell: `.\scripts\evaluar_conectividad.ps1`.
* Para el modo API: la API iniciada (`bash ../fixture2030-hito-10-api-integrada/scripts/iniciar_api.sh`).

Ninguna herramienta es obligatoria para empezar. Si falta un driver, sus capas quedan en SKIP. El modo TCP solo usa la biblioteca estándar de Python. En la notebook no hay `mongosh`, `cqlsh` ni `redis-cli` instalados: los CLI oficiales se ejecutan dentro de cada contenedor (ver más abajo).

## Configuración (sin secretos)

Cada variable se toma, de menor a mayor prioridad, de:

1. valores por defecto de [`scripts/conectividad/config.py`](scripts/conectividad/config.py), sin secretos;
2. `../fixture2030-hito-10-api-integrada/.env`, la misma configuración que usa la API;
3. `config/conectividad.env` (opcional y excluido del repositorio): copiar [`config/configuracion-ejemplo.env`](config/configuracion-ejemplo.env);
4. variables de entorno, que permiten simular un escenario sin editar archivos: `MONGO_HOST=mongodb bash scripts/prueba_tcp.sh`.

La salida informa el **origen** de cada valor y nunca muestra un secreto: solo
"(definida, oculta)", "(vacía)" o "(sin completar)". Todas las variables y sus
diferencias entre la notebook y la red Docker están en
[`docs/topologia_y_entornos.md`](docs/topologia_y_entornos.md#4-variables-por-entorno).

## Orden de ejecución

Desde `fixture2030-hito-11-conectividad/`:

```bash
# 0. Bases levantadas y API iniciada (en otra terminal)
docker compose -f ../docker-compose.yml up -d
bash ../fixture2030-hito-10-api-integrada/scripts/iniciar_api.sh

# 1. Puertos: configuración + resolución + TCP + estado del contenedor (sin drivers)
bash scripts/prueba_tcp.sh

# 2. Clientes nativos: protocolo, identidad, contexto, lectura mínima y sondas
bash scripts/prueba_clientes_nativos.sh                 # + --cli-contenedor para los CLI oficiales

# 3. API: rutas del Hito 10 con request ID y log asociado
bash scripts/prueba_api.sh

# 4. Todo junto, con la matriz de conectividad (opcional: --json / --markdown)
bash scripts/evaluar_conectividad.sh

# 5. Origen alternativo: el mismo diagnóstico dentro de la red de Docker Compose
bash scripts/evaluar_desde_red_docker.sh

# 6. Fallas controladas y reversibles
bash scripts/fallo_controlado.sh             # detiene y reinicia MongoDB; verifica datos y volumen
bash scripts/escenarios_configuracion.sh     # host/puerto/contexto/credencial/timeout + API temporal

# 7. Regenerar toda la evidencia de docs/evidencia/ (unos 2 minutos)
bash scripts/generar_evidencia.sh

# 8. Limpieza opcional (instancias temporales y claves diag:h11:*; no toca datos)
bash scripts/limpieza.sh
```

Opciones del evaluador (`bash scripts/evaluar_conectividad.sh --help`):

| Opción | Uso |
|---|---|
| `--modo completo\|config\|tcp\|nativo\|api` | Qué capas se ejecutan. También se aceptan `--tcp-only`, `--native-only`, `--api-only`, `--config-only` (como el script de referencia de la cátedra) |
| `--producto mongodb,redis` | Evalúa solo esos productos (RNF13: no hace falta que todos estén disponibles) |
| `--capas protocolo,autenticacion` | Ejecuta capas sueltas |
| `--sin-sondas` | Omite las sondas negativas (inexistentes, errores esperados) |
| `--json archivo` / `--markdown archivo` | Guarda resultados y matriz |
| `--estricto` | Código de salida 1 si hay algún FAIL (para automatizar); por defecto siempre 0 |

Pruebas del propio diagnóstico (sin bases): `../fixture2030-hito-10-api-integrada/.venv/Scripts/python -m pytest tests -q` (21 pruebas).

## Estructura

```
fixture2030-hito-11-conectividad/
├── README.md
├── requirements.txt               mismos drivers que la API (el modo TCP no necesita ninguno)
├── config/
│   ├── configuracion-ejemplo.env  todas las variables, sin secretos
│   └── .gitignore                 excluye cualquier *.env real
├── scripts/
│   ├── evaluar_conectividad.sh|.py|.ps1   punto de entrada: modos, matriz, JSON/Markdown
│   ├── prueba_tcp.sh                      modo puertos
│   ├── prueba_clientes_nativos.sh         modo clientes nativos (+ CLI en contenedor)
│   ├── prueba_api.sh                      modo API
│   ├── clientes_en_contenedor.sh          mongosh, cypher-shell, cqlsh, redis-cli, influxdb3, iris session
│   ├── evaluar_desde_red_docker.sh        mismo diagnóstico desde la red de Compose
│   ├── fallo_controlado.sh                MongoDB detenido y recuperado
│   ├── escenarios_configuracion.sh        configuración errónea y corrección; API temporal mal configurada
│   ├── generar_evidencia.sh               regenera docs/evidencia/
│   ├── redactar.py                        filtro de secretos y verificación de la evidencia
│   ├── limpieza.sh                        limpieza opcional
│   └── conectividad/                      paquete Python (RNF15)
│       ├── config.py                      configuración externa y ocultamiento de secretos
│       ├── red.py                         resolución, TCP, HTTP (solo biblioteca estándar)
│       ├── productos/                     una cadena de capas por producto
│       ├── api.py                         rutas de la API con request ID y log
│       └── registro.py                    resultados, cadena, matriz y redacción
├── tests/test_diagnostico.py      pruebas unitarias del diagnóstico
└── docs/
    ├── mapa_de_dependencias.md
    ├── topologia_y_entornos.md
    ├── capas_y_pruebas.md          capas, pruebas nativas y pruebas de API
    ├── matriz_de_conectividad.md
    ├── diagnostico_de_fallas.md    fallo controlado, escenarios y comportamiento de la API
    ├── health_readiness.md
    ├── limitaciones_y_coherencia.md
    └── evidencia/                  salidas redactadas, JSON, logs y verificación de secretos
```

## Cambios en la API del Hito 10

Este hito agrega a [`../fixture2030-hito-10-api-integrada`](../fixture2030-hito-10-api-integrada) (versión 1.1.0):

* `GET /health/live`, `GET /health/ready` y `GET /health/dependencias` con estados `up`, `down`, `degraded`, `unknown` y `not_configured`, y un chequeo profundo reutilizado durante `HEALTH_CACHE_TTL_S` (ver [`docs/health_readiness.md`](docs/health_readiness.md)). `GET /health` del Hito 10 se mantiene sin cambios de contrato.
* Traducción de `Neo.ClientError.Database.DatabaseNotFound` a 503 (antes 500).
* Verificación única del contexto de MongoDB: una database incorrecta da 503 y no un 404 falso.
* 14 pruebas unitarias nuevas (136 en total) y el contrato `openapi/openapi.yaml` regenerado.

## Trazabilidad con el enunciado

| Requisito | Dónde |
|---|---|
| RF1, RF2 | [`mapa_de_dependencias.md`](docs/mapa_de_dependencias.md), [`topologia_y_entornos.md`](docs/topologia_y_entornos.md) |
| RF3, RNF7, RNF8 | `config/`, `scripts/conectividad/config.py`, `scripts/redactar.py`, [`evidencia/verificacion_secretos.txt`](docs/evidencia/verificacion_secretos.txt) |
| RF4, RF5, 5.3 | `scripts/prueba_tcp.sh`, `conectividad/red.py`, [`capas_y_pruebas.md` §3](docs/capas_y_pruebas.md#3-prueba-tcp-y-tipos-de-falla) |
| RF6–RF14, RNF4 | `conectividad/productos/*.py`, [`capas_y_pruebas.md` §4](docs/capas_y_pruebas.md#4-pruebas-por-producto) |
| RF15, RF19, 5.5 | `conectividad/api.py`, [`capas_y_pruebas.md` §6](docs/capas_y_pruebas.md#6-pruebas-de-la-api-55), [`evidencia/logs_api_h11.txt`](docs/evidencia/logs_api_h11.txt) |
| RF16, RNF9, RNF18 | [`matriz_de_conectividad.md`](docs/matriz_de_conectividad.md) |
| RF17, RF18, RNF10, RNF12 | [`diagnostico_de_fallas.md`](docs/diagnostico_de_fallas.md) |
| RF20, RF21, 5.7 | `scripts/fallo_controlado.sh`, `scripts/escenarios_configuracion.sh`, [`diagnostico_de_fallas.md`](docs/diagnostico_de_fallas.md) |
| 5.6 | [`health_readiness.md`](docs/health_readiness.md) |
| 5.8, RNF13, RNF15 | `scripts/evaluar_conectividad.*` (modos, productos, capas, resumen, SKIP) |
| RNF3 | `scripts/evaluar_desde_red_docker.sh`, [`topologia_y_entornos.md`](docs/topologia_y_entornos.md) |
| RNF5 | `TCP_TIMEOUT_S`, `TIMEOUT_CONEXION_S`, `TIMEOUT_OPERACION_S`, `API_TIMEOUT_S`, límite por hilo para IRIS |
| RNF6 | Solo lecturas, `ping`, handshakes y `RETURN 1`. Única escritura: la sonda opcional de Redis (`diag:h11:*`, 1,5 s de vida) |
| RNF17, Limitaciones, Coherencia | [`limitaciones_y_coherencia.md`](docs/limitaciones_y_coherencia.md) |

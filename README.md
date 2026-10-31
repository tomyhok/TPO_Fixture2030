# TPO Fixture 2030

**Repositorio:** https://github.com/tomyhok/TPO_Fixture2030

Proyecto de Ingenieria de Datos II para modelar la informacion del Fixture 2030
con seis motores de persistencia NoSQL, API REST integrada, evaluacion de conectividad,
pruebas de carga y monitoreo con Prometheus + Grafana:

- **MongoDB** (Hito 4): modelo documental de equipos y jugadores.
- **Neo4j** (Hito 5): modelo de grafos para representar equipos, jugadores,
  partidos, sedes y eventos deportivos.
- **Cassandra** (Hito 6): modelo tabular de columnas anchas para el modulo de
  comentarios masivos de los partidos.
- **Redis** (Hito 7): base clave/valor en memoria para sesiones de usuarios,
  cache de consultas frecuentes y contadores en vivo.
- **InfluxDB** (Hito 8): base de series temporales (InfluxDB 3 Core) para métricas en vivo.
- **IRIS** (Hito 9): base orientada a objetos / multimodelo para gestionar 
  entidades complejas con relaciones directas y validaciones encapsuladas.
- **API REST integrada** (Hito 10): API HTTP (FastAPI) que expone los seis
  modulos mediante adaptadores separados, con contrato OpenAPI, pruebas y endpoint `/metrics`.
- **Evaluacion de conectividad** (Hito 11): diagnostico reproducible, capa por
  capa, de la conexion entre la API y los seis productos, con matriz de
  conectividad, fallas controladas y liveness/readiness en la API.
- **Pruebas de carga y optimizacion** (Hito 12): pruebas de carga y optimizacion
  del muro de comentarios en vivo (Cassandra + Redis), integracion conceptual con
  Data Mart y comparacion relacional condicionada. Ver
  [`fixture2030-hito-12-carga-optimizacion/`](fixture2030-hito-12-carga-optimizacion/README.md).
- **Monitoreo y defensa final** (Hito 13): observabilidad con Prometheus, Grafana y
  Node Exporter integrada con `/metrics` de la API, alertas, prueba controlada y
  material de defensa ante la FIFA. Ver
  [`fixture2030-hito-13-monitoreo/`](fixture2030-hito-13-monitoreo/README.md).

## Requisitos

- Docker Desktop con Docker Compose.
- Puertos disponibles: `27017`, `7474`, `7687`, `9042`, `6379`, `8181`, `1972`,
  `52773`, `8000` (API del Hito 10), `9090` (Prometheus), `3000` (Grafana) y `9100` (Node Exporter).
- Python 3 en el host para el generador de datos de Cassandra, y Python 3.12
  para la API del Hito 10.

No es necesario instalar MongoDB, `mongosh`, Neo4j, `cqlsh` ni `redis-cli` localmente: las
herramientas se ejecutan dentro de los containers.

## Inicio rapido

Ejecutar desde esta carpeta, que contiene el `docker-compose.yml` principal:

Crear `.env` a partir de [`.env.example`](.env.example) y completar las contraseñas
locales antes del primer inicio. Si los volúmenes ya existen, usar sus credenciales
actuales: modificar `.env` no cambia la contraseña almacenada por el motor.
El archivo `.env` queda excluido de Git. La API usa su propio `.env` del Hito 10,
que debe contener las mismas credenciales de MongoDB y Neo4j.

```powershell
docker compose up -d
docker compose ps
```

Los servicios disponibles son:

| Servicio | Uso | Acceso |
|---|---|---|
| `mongodb` | Base documental | `localhost:27017` |
| `neo4j` | Base de grafos | Browser: `http://localhost:7474` |
| `neo4j` | Protocolo Bolt | `neo4j://localhost:7687` |
| `cassandra` | Base tabular de columnas anchas | `localhost:9042` |
| `redis` | Base clave/valor en memoria | `localhost:6379` |
| `influxdb` | Base temporal InfluxDB 3 Core | `localhost:8181` |
| `iris` | Base de objetos y multimodelo | `localhost:1972` (Portal: `52773`) |

Para detener los servicios sin borrar los datos:

```powershell
docker compose down
```

No ejecutar `docker compose down -v` salvo que se quieran eliminar los
volumenes y comenzar desde cero.

## MongoDB

### Credenciales

- Usuario: `admin`
- Contrasena: valor local de `MONGO_PASSWORD` en `.env` (no se publica).
- Base de datos: `fixture2030`

### Verificar la conexion

```powershell
docker compose exec mongodb mongosh `
  -u admin `
  --authenticationDatabase admin `
  fixture2030 `
  --eval "db.runCommand({ ping: 1 })"
```

Para verificar los datos principales:

```powershell
docker compose exec mongodb mongosh `
  -u admin `
  --authenticationDatabase admin `
  fixture2030 `
  --eval "printjson({ equipos: db.equipos.countDocuments(), jugadores: db.jugadores.countDocuments() })"
```

El resultado esperado es `64` equipos y `1472` jugadores.

En MongoDB Compass configurar el usuario de `.env`, su contraseña local y `authSource=admin`. La dirección sin credenciales es:

```text
mongodb://localhost:27017/fixture2030?authSource=admin
```

### Scripts de MongoDB

Los scripts de `fixture2030-mongoDB/init-scripts/` se ejecutan
automaticamente y en orden cuando MongoDB inicia con un volumen vacio:

1. `01-colecciones.js`: crea las colecciones y sus validaciones.
2. `02-carga.js`: carga equipos y jugadores desde los JSON.
3. `03-indices.js`: crea los indices.

Para ejecutar manualmente una carga idempotente:

```powershell
docker compose exec mongodb mongosh `
  -u admin `
  --authenticationDatabase admin `
  fixture2030 `
  --file /docker-entrypoint-initdb.d/02-carga.js
```

Las consultas adicionales se encuentran en `fixture2030-mongoDB/queries/`.

## Neo4j

### Credenciales

- Usuario: `neo4j`
- Contrasena: valor local de `NEO4J_PASSWORD` en `.env` (no se publica).
- Browser: `http://localhost:7474`
- Bolt: `neo4j://localhost:7687`

### Preparar los archivos de importacion

Los scripts de Neo4j usan los JSON generados por el modulo MongoDB. Copiarlos
al volumen de importacion:

```powershell
docker cp fixture2030-mongoDB/init-scripts/data/equipos.json `
  fixture2030-neo4j:/var/lib/neo4j/import/

docker cp fixture2030-mongoDB/init-scripts/data/jugadores.json `
  fixture2030-neo4j:/var/lib/neo4j/import/
```

### Ejecutar los scripts Cypher

Abrir Neo4j Browser y ejecutar los archivos de
`fixture2030-neo4j/queries/` en este orden:

1. `estructura.cypher`: restricciones e indices.
2. `carga.cypher`: nodos, relaciones y datos de ejemplo.
3. `crud.cypher`: operaciones CRUD sobre un evento de prueba.
4. `consultas_grafo.cypher`: consultas relacionales y analisis del grafo.

La carga utiliza `MERGE`, por lo que puede ejecutarse nuevamente sin generar
duplicados para las entidades con identificadores definidos.


## Cassandra

Modulo de comentarios masivos del Hito 6. La guia detallada esta en
[`fixture2030-cassandra/README.md`](fixture2030-cassandra/README.md).

### Acceso

- Puerto CQL: `localhost:9042`
- Keyspace: `fixture2030`
- Sin autenticacion (ambiente local de desarrollo)

Los datos de Cassandra se guardan en el volumen nombrado Docker
`fixture2030_cassandra_data`, conforme al RNF2 del Hito 6. La migracion del
bind mount anterior se documento y no borro el directorio original.

### Verificar la conexion

Cassandra tarda entre 60 y 120 segundos en aceptar conexiones la primera vez.

```powershell
docker compose exec cassandra nodetool status
docker compose exec cassandra cqlsh -e "SHOW VERSION"
```

### Scripts de Cassandra

Los scripts de `fixture2030-cassandra/scripts/` estan montados dentro del
contenedor en `/scripts` y se ejecutan en este orden:

```powershell
docker compose exec cassandra cqlsh -f /scripts/01-keyspace.cql
docker compose exec cassandra cqlsh -f /scripts/02-tablas.cql
docker compose exec cassandra cqlsh -f /scripts/03-carga-muestra.cql
docker compose exec cassandra cqlsh -f /scripts/04-crud.cql
docker compose exec cassandra cqlsh -f /scripts/05-consultas.cql
```

1. `01-keyspace.cql`: keyspace, estrategia y factor de replicacion.
2. `02-tablas.cql`: las cuatro tablas y el indice secundario.
3. `03-carga-muestra.cql`: muestra idempotente de 35 comentarios.
4. `04-crud.cql`: operaciones CRUD sobre un comentario de prueba.
5. `05-consultas.cql`: consultas del muro, historial, moderacion y metricas.

### Carga masiva y medicion

Ejecutar desde la carpeta `fixture2030-cassandra`:

```bash
bash tools/carga_masiva.sh 1000000
bash tools/benchmark_escritura.sh 500000 32
docker compose exec cassandra cqlsh --request-timeout=600 -f /scripts/06-medicion.cql
```

Los resultados se registran en `fixture2030-cassandra/docs/evidencia.md`.

## Redis

Modulo de cache de usuarios y sesiones del Hito 7. La guia detallada esta en
[`fixture2030-redis/README.md`](fixture2030-redis/README.md).

### Acceso

- Puerto: `localhost:6379`
- Sin contrasena (ambiente local de desarrollo)
- Datos en el bind mount `~/docker/data/redis` (AOF + RDB)

### Verificar la conexion

```bash
docker compose exec redis redis-cli PING
```

### Scripts de Redis

Los scripts de `fixture2030-redis/scripts/` estan montados en `/scripts`.
Como `redis-cli` no acepta comentarios, se filtran con `grep`:

```bash
docker compose exec redis sh -c "grep -v '^#' /scripts/inicializacion.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/sesiones.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/cache.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/concurrencia.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/metricas.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/limpieza.redis | redis-cli"   # opcional
```

La prueba de concurrencia y la medicion se ejecutan desde `fixture2030-redis`:

```bash
bash tools/prueba_concurrencia.sh 10 1000
bash tools/medicion.sh 20000
bash tools/generar_evidencia.sh   # corre todo en orden y guarda la evidencia
```

Los resultados se registran en `fixture2030-redis/docs/evidencia/README.md`.

## InterSystems IRIS

Módulo de entidades complejas del Hito 9. La guía detallada está en
[`fixture2030-iris/README.md`](fixture2030-iris/README.md).

### Acceso

- Puerto superserver: `localhost:1972`
- Management Portal: `http://localhost:52773/csp/sys/UtilHome.csp`
- Datos en el bind mount `~/docker/data/iris`

### Ingreso y ejecución

Para ingresar al terminal de ObjectScript y probar las clases:

```powershell
docker compose exec iris iris session iris
```

Las instrucciones de carga y demostración se detallan en el README del módulo.

## InfluxDB (Series Temporales)

Módulo de métricas en vivo del Hito 8. La guía detallada está en
[`fixture2030-influxDB/README.md`](fixture2030-influxDB/README.md).

### Acceso

- API HTTP: `localhost:8181`
- Datos en el bind mount `~/docker/data/influxdb`

### Ingreso y ejecución

Para inicializar la base, cargar lotes y probar consultas, ir al módulo y usar los scripts Bash
(los pasos completos están en el README del módulo).

```bash
cd fixture2030-influxDB
bash scripts/inicializacion.sh
```

## API REST integrada (Hito 10)

API que integra los seis modulos. La guia completa (configuracion, preparacion
de datos, ejecucion, pruebas y evidencia) esta en
[`fixture2030-hito-10-api-integrada/README.md`](fixture2030-hito-10-api-integrada/README.md).

```bash
cd fixture2030-hito-10-api-integrada
cp .env.example .env                 # completar las contrasenas
bash scripts/preparar_datos.sh       # datos de muestra de las seis fuentes
bash scripts/iniciar_api.sh          # Swagger UI: http://127.0.0.1:8000/docs | Métricas: /metrics
```

> **Cambio en IRIS:** `ISC_DATA_DIRECTORY` paso de `/durable` a `/durable/iris`
> (recomendacion de InterSystems). Con `/durable`, IRIS exige un directorio
> vacio y no volvia a iniciar sobre el bind mount `~/docker/data/iris` con datos.

## Evaluacion de conectividad (Hito 11)

Diagnostico por capas (configuracion, resolucion, TCP, protocolo,
autenticacion, autorizacion, contexto, lectura y API) de los seis productos,
desde el mismo origen que la API. Guia completa en
[`fixture2030-hito-11-conectividad/README.md`](fixture2030-hito-11-conectividad/README.md).

```bash
cd fixture2030-hito-11-conectividad
bash scripts/prueba_tcp.sh                 # puertos (sin drivers)
bash scripts/prueba_clientes_nativos.sh    # clientes nativos y sondas
bash scripts/prueba_api.sh                 # rutas de la API con request ID (API iniciada)
bash scripts/evaluar_conectividad.sh       # todo + matriz de conectividad
```

## Pruebas de carga y optimizacion (Hito 12)

Pruebas de carga sostenida, triangulacion de cuello de botella, optimizacion con
muro precomputado en Redis sobre Cassandra, validacion de integridad post-carga,
integracion conceptual con Data Mart y comparacion relacional condicionada. Guia
completa en
[`fixture2030-hito-12-carga-optimizacion/README.md`](fixture2030-hito-12-carga-optimizacion/README.md).

```bash
cd fixture2030-hito-12-carga-optimizacion
python scripts/preparar_datos.py --filas 100000 --semilla 2030
bash scripts/ejecutar_linea_base.sh --tasa 10
bash scripts/ejecutar_prueba_optimizada.sh --tasa 10
python scripts/comparar_resultados.py docs/evidencia/resultados/base_X.json docs/evidencia/resultados/optimizado_Y.json
python scripts/limpiar_datos_de_prueba.py --confirmar   # opcional
```

## Monitoreo y defensa final (Hito 13)

Observabilidad transversal con Prometheus, Grafana y Node Exporter integrada con
`GET /metrics` de la API del Hito 10, reglas de alerta, prueba controlada reversible
y defensa técnica ante la FIFA. Guía completa en
[`fixture2030-hito-13-monitoreo/README.md`](fixture2030-hito-13-monitoreo/README.md).

```bash
cd fixture2030-hito-13-monitoreo
bash scripts/iniciar_monitoreo.sh            # Prometheus :9090, Grafana :3000, Node Exporter :9100
bash scripts/verificar_targets.sh            # Verifica targets UP y reglas en Prometheus
bash scripts/ejecutar_prueba_controlada.sh   # Prueba de falla reversible (3 fases)
bash scripts/limpiar_entorno.sh              # Detiene monitoreo sin borrar volúmenes
```

## Estructura del proyecto

Las correcciones posteriores a la devolución docente están explicadas en
[el walkthrough de los hitos 4 a 10](docs/walkthrough_correcciones_feedback.md),
incluyendo evidencia nueva, compatibilidad del Hito 11 y el token pendiente de InfluxDB.

```text
docker-compose.yml                 Compose unificado de los seis motores
fixture2030-mongoDB/
  init-scripts/                     Inicializacion y datos JSON de MongoDB
  schemas/                          Validaciones JSON Schema
  queries/                          Operaciones y consultas MongoDB
  docs/                             Documentacion del modelo documental
  docker-compose.yml                Compose independiente del modulo
fixture2030-neo4j/
  queries/                          Scripts de estructura, carga y consultas
  docs/                             Documentacion del modelo de grafos
  docker-compose.yml                Compose independiente del modulo
  import/                            Archivos auxiliares de importacion
fixture2030-cassandra/
  scripts/                          Scripts CQL de esquema, carga, CRUD y medicion
  tools/                            Generador de datos y pruebas de rendimiento
  data/                             CSV generados (no se versionan)
  docs/                             Analisis, modelo tabular y evidencia
  docker-compose.yml                Compose independiente del modulo
fixture2030-redis/
  scripts/                          Scripts redis-cli de carga, sesiones, cache y metricas
  tools/                            Prueba de concurrencia, medicion y evidencia
  docs/                             Patrones de acceso, modelo, ciclo de vida y evidencia
  docker-compose.yml                Compose independiente del modulo
fixture2030-influxDB/
  scripts/                          Scripts de Inicialización, Python Generator (LP) y Bash para la API
  docs/                             Análisis de cardinalidad, retención y modelo
  README.md                         Documentación del modelo temporal InfluxDB 3 Core
  docker-compose.yml                Compose independiente del modulo
fixture2030-iris/
  scripts/                          Scripts de clases (XML/UDL) y rutinas operativas MAC
  docs/evidencia/                   Capturas de validación y ejecución
  README.md                         Documentación del modelo, UML y matriz de integridad
  docker-compose.yml                Compose independiente del modulo
fixture2030-hito-10-api-integrada/
  app/                              API: rutas, servicios, adaptadores, schemas, config y /metrics
  openapi/                          Contrato OpenAPI generado del codigo
  scripts/                          Inicio, preparacion de datos, conectividad, pruebas y evidencia
  tests/                            Pruebas unitarias y de integracion
  docs/                             Casos de uso, arquitectura, contratos, conectividad y evidencia
fixture2030-hito-11-conectividad/
  scripts/                          Evaluador por capas (modos tcp/nativo/api/completo), fallas controladas y evidencia
  config/                           Configuracion de ejemplo sin secretos
  tests/                            Pruebas unitarias del diagnostico
  docs/                             Mapa de dependencias, topologia, matriz, fallas, health/readiness y evidencia
fixture2030-hito-12-carga-optimizacion/
  config/                           Variables de entorno de ejemplo sin secretos
  scripts/                          Preparacion, generador de carga, comparacion, integridad y limpieza
  datos-o-generadores/              Descripcion de semilla, distribuciones y generacion reproducible
  docs/                             Flujo, linea base, hipotesis, Data Mart, comparacion relacional y evidencia
fixture2030-hito-13-monitoreo/
  prometheus/                       Reglas de alerta de Prometheus
  grafana/                          Provisioning automatico y dashboard War Room (JSON)
  scripts/                          Inicio, verificacion de targets, prueba controlada y limpieza
  docs/                             Inventario, PromQL, alertas, decisiones, limitaciones y defensa FIFA
  evidencia/                        Salidas de targets, prueba de falla, vista dashboard y escaneo de secretos
  defensa/                          Presentacion HTML interactiva, guion de 20 minutos y estrategia de demo
```

Los Compose dentro de los modulos se conservan como referencia y para ejecutar
cada modulo por separado. Para el proyecto completo se debe usar el Compose de
la raiz. No levantar los Compose de los modulos y el de la raiz al mismo tiempo:
comparten nombres de contenedor y puertos.

## Persistencia y reinicio desde cero

Los datos se almacenan en volumenes Docker y sobreviven a `stop`, `restart` y
`down`. Los scripts de inicializacion de MongoDB no se vuelven a ejecutar si el
volumen ya contiene una base.

Para reiniciar desde cero, detener el entorno y eliminar los volumenes
correspondientes de forma consciente:

```powershell
docker compose down -v
```

Luego volver a ejecutar `docker compose up -d` y repetir la preparacion y carga
de Neo4j.

Cassandra ahora usa un volumen nombrado; Redis, IRIS e InfluxDB mantienen
sus directorios persistentes del host. No usar `down -v` si se quieren conservar
los volumenes de MongoDB, Neo4j y Cassandra. El directorio antiguo de Cassandra
se conserva como respaldo y ya no es el almacenamiento activo.

Los volumenes Docker son locales a cada computadora y no se versionan en Git.
El Compose crea los volumenes automaticamente si no existen. Por eso, otro
integrante puede ejecutar `docker compose up -d` despues de clonar el proyecto,
pero tendra una instancia independiente y debera cargar Neo4j siguiendo los
pasos anteriores.

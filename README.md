# TPO Fixture 2030

Proyecto de Ingenieria de Datos II para modelar la informacion del Fixture 2030
con tres motores de persistencia:

- **MongoDB** (Hito 4): modelo documental de equipos y jugadores.
- **Neo4j** (Hito 5): modelo de grafos para representar equipos, jugadores,
  partidos, sedes y eventos deportivos.
- **Cassandra** (Hito 6): modelo tabular de columnas anchas para el modulo de
  comentarios masivos de los partidos.
- **Redis** (Hito 7): base clave/valor en memoria para sesiones de usuarios,
  cache de consultas frecuentes y contadores en vivo.

## Requisitos

- Docker Desktop con Docker Compose.
- Puertos disponibles: `27017`, `7474`, `7687`, `9042` y `6379`.
- Python 3 en el host, solo para el generador de datos de Cassandra.

No es necesario instalar MongoDB, `mongosh`, Neo4j, `cqlsh` ni `redis-cli` localmente: las
herramientas se ejecutan dentro de los containers.

## Inicio rapido

Ejecutar desde esta carpeta, que contiene el `docker-compose.yml` principal:

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

Para detener los servicios sin borrar los datos:

```powershell
docker compose down
```

No ejecutar `docker compose down -v` salvo que se quieran eliminar los
volumenes y comenzar desde cero.

## MongoDB

### Credenciales

- Usuario: `admin`
- Contrasena: `password123`
- Base de datos: `fixture2030`

### Verificar la conexion

```powershell
docker compose exec mongodb mongosh `
  -u admin -p password123 `
  --authenticationDatabase admin `
  fixture2030 `
  --eval "db.runCommand({ ping: 1 })"
```

Para verificar los datos principales:

```powershell
docker compose exec mongodb mongosh `
  -u admin -p password123 `
  --authenticationDatabase admin `
  fixture2030 `
  --eval "printjson({ equipos: db.equipos.countDocuments(), jugadores: db.jugadores.countDocuments() })"
```

El resultado esperado es `64` equipos y `1472` jugadores.

La conexion desde MongoDB Compass es:

```text
mongodb://admin:password123@localhost:27017/fixture2030?authSource=admin
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
  -u admin -p password123 `
  --authenticationDatabase admin `
  fixture2030 `
  --file /docker-entrypoint-initdb.d/02-carga.js
```

Las consultas adicionales se encuentran en `fixture2030-mongoDB/queries/`.

## Neo4j

### Credenciales

- Usuario: `neo4j`
- Contrasena: `fixture2030`
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

A diferencia de MongoDB y Neo4j, los datos de Cassandra **no** se guardan en un
volumen Docker sino en un bind mount en `~/docker/data/cassandra`, segun la
convencion de la materia.

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

## Estructura del proyecto

```text
docker-compose.yml                 Compose unificado de MongoDB, Neo4j, Cassandra y Redis
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

Los datos de Cassandra y Redis no viven en un volumen Docker, asi que `down -v`
no los borra. Para reiniciar ese modulo desde cero hay que eliminar el bind mount de
forma consciente:

```bash
docker compose down
rm -rf ~/docker/data/cassandra
rm -rf ~/docker/data/redis
```

Los volumenes Docker son locales a cada computadora y no se versionan en Git.
El Compose crea los volumenes automaticamente si no existen. Por eso, otro
integrante puede ejecutar `docker compose up -d` despues de clonar el proyecto,
pero tendra una instancia independiente y debera cargar Neo4j siguiendo los
pasos anteriores.
# TPO Fixture 2030

Proyecto de Ingenieria de Datos II para modelar la informacion del Fixture 2030
con dos motores de persistencia:

- **MongoDB**: modelo documental de equipos y jugadores.
- **Neo4j**: modelo de grafos para representar equipos, jugadores, partidos,
  sedes y eventos deportivos.

## Requisitos

- Docker Desktop con Docker Compose.
- Puertos disponibles: `27017`, `7474` y `7687`.

No es necesario instalar MongoDB, `mongosh` ni Neo4j localmente: las herramientas
se ejecutan dentro de los containers.

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

## Estructura del proyecto

```text
docker-compose.yml                 Compose unificado de MongoDB y Neo4j
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
```

Los dos Compose dentro de los modulos se conservan como referencia y para
ejecutar cada modulo por separado. Para el proyecto completo se debe usar el
Compose de la raiz. No levantar los tres Compose al mismo tiempo.

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

Los volumenes Docker son locales a cada computadora y no se versionan en Git.
El Compose crea los volumenes automaticamente si no existen. Por eso, otro
integrante puede ejecutar `docker compose up -d` despues de clonar el proyecto,
pero tendra una instancia independiente y debera cargar Neo4j siguiendo los
pasos anteriores.
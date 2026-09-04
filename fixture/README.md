# Fixture 2030 — Modulo documental de equipos y jugadores

Primer modulo de persistencia de la plataforma del Fixture 2030, implementado en
MongoDB: almacena, recupera y actualiza los 64 equipos del torneo y sus 1472
jugadores.

## Requisitos

Solo Docker y Docker Compose. Los scripts se ejecutan con `mongosh`, que ya viene
dentro de la imagen `mongo:7.0`, asi que no hace falta instalar MongoDB ni ninguna
otra herramienta en la maquina.

## Estructura

```
docker-compose.yml            ambiente local de MongoDB
init-scripts/                 inicializacion y carga de datos
  01-colecciones.js             crea las colecciones con sus validaciones
  02-carga.js                   carga los equipos y jugadores
  03-indices.js                 crea los indices
  data/                         datos de origen en JSON
schemas/                      diseno y validacion documental
  equipos.schema.js
  jugadores.schema.js
queries/                      operaciones de carga y recuperacion
  01-operaciones.js             inserciones y actualizaciones
  02-consultas.js               filtros, proyecciones, orden y paginacion
  03-agregacion.js              agregacion de goles por confederacion
  04-explain.js                 analisis de eficiencia con explain()
docs/
  Decisiones_Tecnicas.md        decisiones de diseno y evidencia de pruebas
README.md
```

## Variables de entorno

Se definen en `docker-compose.yml`, en la seccion `environment` del servicio
`mongodb`:

| Variable | Valor | Para que sirve |
|---|---|---|
| `MONGO_INITDB_ROOT_USERNAME` | `admin` | Usuario administrador que crea la imagen al inicializarse |
| `MONGO_INITDB_ROOT_PASSWORD` | `password123` | Contrasena de ese usuario |
| `MONGO_INITDB_DATABASE` | `fixture2030` | Base sobre la que se ejecutan los scripts de `init-scripts/` |

## Inicio y verificacion

```bash
docker compose up -d
docker compose ps
```

Al levantarse por primera vez, MongoDB ejecuta solo los scripts de
`init-scripts/` en orden. Se puede verificar en los logs:

```bash
docker compose logs mongodb | grep -E "Coleccion|cargados|sin equipo"
```

Tiene que aparecer:

```
Coleccion 'equipos' creada con validacion.
Coleccion 'jugadores' creada con validacion.
Equipos cargados:   64
Jugadores cargados: 1472
Jugadores sin equipo valido: 0
```

## Ejecutar los scripts

Todos los comandos siguen esta forma:

```bash
docker compose exec mongodb mongosh \
  -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file <ruta del script>
```

Las rutas dentro del contenedor son `/docker-entrypoint-initdb.d/` para los
scripts de inicializacion y `/queries/` para los de recuperacion:

```bash
# Volver a ejecutar la carga (es idempotente: no genera duplicados)
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file /docker-entrypoint-initdb.d/02-carga.js

# Inserciones y actualizaciones
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file /queries/01-operaciones.js

# Consultas de recuperacion
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file /queries/02-consultas.js

# Agregacion
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file /queries/03-agregacion.js

# Analisis de eficiencia
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --file /queries/04-explain.js
```

## Conectarse a mano

```bash
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin fixture2030
```

Desde afuera del contenedor, con Compass o cualquier cliente:

```
mongodb://admin:password123@localhost:27017/fixture2030?authSource=admin
```

## Persistencia

Los datos viven en el volumen `mongodb_data`, asi que sobreviven a
`docker compose restart` y a `docker compose stop`. Para verificarlo:

```bash
docker compose restart
docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
  fixture2030 --eval 'db.jugadores.countDocuments()'
```

## Gestion

```bash
docker compose ps                # estado de los servicios
docker compose logs mongodb      # logs
docker compose down              # parar (los datos se conservan)
docker compose down -v           # parar y borrar los datos
```

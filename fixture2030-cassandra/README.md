# TPO Fixture 2030 — Módulo de Comentarios Masivos (Apache Cassandra)

Este directorio contiene el entorno local, el modelo tabular y los scripts CQL
del **Hito 6** del proyecto Fixture 2030 (Ingeniería de Datos II). El módulo
resuelve la publicación y recuperación de comentarios de los partidos en un
escenario de escritura intensiva y alta concurrencia.

## 📋 Requisitos previos

* Docker y Docker Desktop (o Docker Engine) con Docker Compose.
* Python 3 en el host, solo para el generador de datos (usa únicamente la
  biblioteca estándar; no hay que instalar nada).
* Puerto `9042` libre.

No hace falta instalar Cassandra ni `cqlsh` localmente: todo se ejecuta dentro
del contenedor.

---

## 🚀 Guía de inicio rápido (reproducibilidad)

Siga estos pasos exactos, en orden, desde la carpeta `fixture2030-cassandra`.

### 1. Levantar el entorno

```bash
docker compose up -d
```

Este comando usa la imagen `cassandra:latest` (RNF1) y persiste los datos en
`~/docker/data/cassandra` (RNF2).

### 2. Verificar que el nodo esté disponible

Cassandra tarda entre 60 y 120 segundos en aceptar conexiones la primera vez.
Esperar hasta que el nodo figure como `UN` (Up / Normal):

```bash
docker compose exec cassandra nodetool status
```

```text
--  Address     Load       Tokens  Owns  Host ID   Rack
UN  172.18.0.2  120 KiB    16      100%  ...       rack1
```

Y que el cliente CQL responda:

```bash
docker compose exec cassandra cqlsh -e "SHOW VERSION; DESCRIBE KEYSPACES;"
```

> Anotar la versión que devuelve `SHOW VERSION` en `docs/evidencia.md`: como el
> Compose usa la etiqueta `latest`, es el único registro de qué se probó.

### 3. Crear el esquema

```bash
docker compose exec cassandra cqlsh -f /scripts/01-keyspace.cql
docker compose exec cassandra cqlsh -f /scripts/02-tablas.cql
```

### 4. Cargar la muestra de desarrollo

35 comentarios sobre 3 partidos, suficientes para validar todas las consultas:

```bash
docker compose exec cassandra cqlsh -f /scripts/03-carga-muestra.cql
```

El script es idempotente (RNF7): puede reejecutarse sin duplicar filas. La única
excepción son los contadores del bloque 4, que por naturaleza vuelven a sumar.

### 5. Ejecutar CRUD y consultas

```bash
docker compose exec cassandra cqlsh -f /scripts/04-crud.cql
docker compose exec cassandra cqlsh -f /scripts/05-consultas.cql
```

### 6. Carga masiva (más de 1.000.000 de comentarios)

```bash
bash tools/carga_masiva.sh 1000000
```

El script genera los CSV con `tools/generar_comentarios.py`, los carga con el
comando `COPY` de `cqlsh` y reporta el tiempo y la tasa obtenida. Para una
prueba rápida: `bash tools/carga_masiva.sh 50000`.

### 7. Medición y evidencia

```bash
docker compose exec cassandra cqlsh --request-timeout=600 -f /scripts/06-medicion.cql
bash tools/benchmark_escritura.sh 500000 32
```

Volcar los resultados en `docs/evidencia.md`, incluyendo fecha, versión
observada de Cassandra y recursos de la notebook (RNF9).

### Sesión interactiva

```bash
docker compose exec cassandra cqlsh -k fixture2030
```

### Detener el entorno

```bash
docker compose down          # conserva los datos en ~/docker/data/cassandra
```

Para empezar de cero hay que borrar el bind mount a mano, de forma consciente:

```bash
docker compose down
rm -rf ~/docker/data/cassandra
```

---

## 🧩 El modelo en una pantalla

Cinco consultas prioritarias, cuatro tablas y un índice. Ninguna tabla existe
sin una consulta que la justifique (RNF4).

| Consulta | Tabla | Clave primaria |
|---|---|---|
| Q1 — últimos comentarios de un partido, en vivo | `comentarios_por_partido` | `((id_partido, ventana, shard), id_comentario DESC)` |
| Q2 — historial mensual de un usuario | `comentarios_por_usuario` | `((id_usuario, periodo), id_comentario DESC)` |
| Q3 — cola de moderación de un partido | `comentarios_en_revision` | `((id_partido, estado_moderacion), id_comentario ASC)` |
| Q4 — likes y reportes de un comentario | `metricas_comentario` | `(id_comentario)` |
| Moderación por idioma dentro de una ventana | `comentarios_por_partido` + `idx_idioma_comentario` | índice secundario local |

**Claves derivadas** que calcula el productor antes de escribir:

| Campo | Formato | Cálculo |
|---|---|---|
| `ventana` | `AAAAMMDDHHMM` | instante truncado al minuto |
| `shard` | `0..3` | `crc32(id_usuario) % 4` |
| `periodo` | `AAAAMM` | instante truncado al mes |

**Por qué esa clave de partición:** un partido popular genera ~5.800.000
comentarios. En una sola partición sería inviable. La ventana de 1 minuto la
corta en ~180.000 filas en el pico, y el `shard` la divide en 4 particiones de
~45.000 filas (~15 MB), repartiendo también la escritura del pico. El costo
aceptado es que Q1 lee 4 particiones en paralelo y ordena en el cliente.

El razonamiento completo, con supuestos de carga, análisis de hotspots, política
de TTL y trade-offs, está en [`docs/analisis_hito6.md`](docs/analisis_hito6.md).

---

## 📂 Estructura del directorio

```text
fixture2030-cassandra/
  docker-compose.yml              Servicio Cassandra, puerto 9042, bind mount de datos
  scripts/
    01-keyspace.cql               Keyspace, estrategia y factor de replicación
    02-tablas.cql                 Tablas, claves primarias e índice secundario
    03-carga-muestra.cql          Muestra idempotente de 35 comentarios
    04-crud.cql                   CREATE / READ / UPDATE / DELETE y counters
    05-consultas.cql              Q1 a Q4 y la comparativa del índice secundario
    06-medicion.cql               Versión, conteos, distribución y tracing
  tools/
    generar_comentarios.py        Generador sintético reproducible (solo stdlib)
    carga_masiva.sh               Generación + COPY + medición de la tasa de carga
    benchmark_escritura.sh        Prueba de escritura con cassandra-stress
    stress_comentarios.yaml       Perfil de stress sobre la tabla real del módulo
  data/                           CSV generados (no se versionan)
  docs/
    analisis_hito6.md             Análisis técnico completo (los 8 apartados)
    modelo_tabular.md             Referencia columna por columna del esquema
    evidencia.md                  Plantilla de registro de la ejecución
    capturas/                     Capturas de pantalla de la evidencia
```

---

## ⚠️ Alcance del ambiente

Este entorno es **un nodo único de aprendizaje**, con `SimpleStrategy` y
`replication_factor = 1`. No es una topología de alta disponibilidad ni
multirregional, y no debe presentarse como tal. Un despliegue real del Fixture
2030 usaría `NetworkTopologyStrategy` con RF=3 por datacenter y escrituras con
`LOCAL_QUORUM`.

Las credenciales del Compose son de desarrollo local: el contenedor corre con el
autenticador por defecto (`AllowAllAuthenticator`) y no expone secretos reales
(RNF8).

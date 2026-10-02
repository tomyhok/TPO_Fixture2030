# TPO Fixture 2030 — Módulo de Caché de Usuarios y Sesiones (Redis)

Este directorio contiene el entorno local, el modelo clave/valor y los scripts
del **Hito 7** del proyecto Fixture 2030 (Ingeniería de Datos II). El módulo
maneja las sesiones de los usuarios, la caché de consultas frecuentes (fichas
de partidos y equipos) y los contadores en vivo de los partidos.

Redis **no reemplaza** a MongoDB (Hito 4), Neo4j (Hito 5) ni Cassandra
(Hito 6): guarda estado temporal y copias de acceso rápido. La fuente de verdad
de los datos cacheados sigue estando en esos módulos.

## 📋 Requisitos previos

* Docker Desktop (o Docker Engine) con Docker Compose.
* Puerto `6379` libre.

No hace falta instalar Redis ni `redis-cli` localmente: todo se ejecuta dentro
del contenedor.

---

## 🚀 Guía de inicio rápido

Siga estos pasos, en orden, desde la carpeta `fixture2030-redis`.

### 1. Levantar el entorno

```bash
docker compose up -d
docker compose ps
```

Usa la imagen `redis:latest` (RNF1) y guarda los datos en `~/docker/data/redis`
(RNF2). Si la imagen no está descargada, Compose la baja sola.

### 2. Verificar el servidor

```bash
docker compose exec redis redis-cli PING
```

Resultado esperado: `PONG`.

### 3. Cómo ejecutar los scripts

`redis-cli` no acepta líneas de comentario, así que los scripts se ejecutan
filtrando las líneas que empiezan con `#`. El comando es siempre el mismo,
cambiando el nombre del archivo:

```bash
docker compose exec redis sh -c "grep -v '^#' /scripts/<script>.redis | redis-cli"
```

### 4. Ejecutar el módulo en orden

```bash
docker compose exec redis sh -c "grep -v '^#' /scripts/inicializacion.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/sesiones.redis | redis-cli"
```

El último bloque de `sesiones.redis` crea una sesión con TTL de 5 segundos.
Esperar unos segundos y comprobar que Redis la borró sola:

```bash
sleep 6
docker compose exec redis redis-cli TTL sesion:S-0199       # -2
docker compose exec redis redis-cli HGETALL sesion:S-0199   # vacío
```

Continuar con:

```bash
docker compose exec redis sh -c "grep -v '^#' /scripts/cache.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/concurrencia.redis | redis-cli"
docker compose exec redis sh -c "grep -v '^#' /scripts/metricas.redis | redis-cli"
```

### 5. Prueba de concurrencia y medición

```bash
bash tools/prueba_concurrencia.sh 10 1000
bash tools/medicion.sh 20000
```

Solo usan `redis-cli` y `bash`; no hace falta instalar nada más.

### 6. Regenerar toda la evidencia

```bash
bash tools/generar_evidencia.sh
```

Ejecuta, en este mismo orden, limpieza, todos los scripts, la verificación de
expiración, la tasa de hit de `cache.redis`, la prueba de concurrencia, la
medición, las métricas y la prueba de persistencia (reinicia el contenedor).
Guarda cada salida en `docs/evidencia/` con fecha. Los resultados de la corrida
de referencia están resumidos en
[`docs/evidencia/README.md`](docs/evidencia/README.md). Como se usa `latest`,
hay que anotar la fecha y la versión de Redis de cada nueva corrida.

### 7. Limpieza (opcional)

Borra solo las claves del módulo. Después se puede volver a correr
`carga_muestra.redis`:

```bash
docker compose exec redis sh -c "grep -v '^#' /scripts/limpieza.redis | redis-cli"
```

### Sesión interactiva

```bash
docker compose exec redis redis-cli
```

### Detener y reiniciar sin perder datos

```bash
docker compose stop          # detiene el contenedor
docker compose start         # lo vuelve a levantar con los mismos datos
docker compose restart redis # reinicio
docker compose down          # elimina el contenedor, NO los datos
```

Los datos están en `~/docker/data/redis` (AOF + RDB), así que sobreviven a
`stop`, `restart` y `down`. Para empezar de cero hay que borrar esa carpeta a
mano, de forma consciente:

```bash
docker compose down
rm -rf ~/docker/data/redis
```

---

## 🧩 El modelo en una pantalla

| Patrón de acceso | Clave | Tipo | TTL |
|---|---|---|---|
| Validar / renovar sesión | `sesion:<id_sesion>` | Hash | 1800 s, renovado con actividad |
| Ficha de partido | `cache:partido:<codigo_partido>` | String (JSON) | 300 s + `DEL` al cambiar en Neo4j |
| Ficha de equipo | `cache:equipo:<codigo_iso>` | String (JSON) | 3600 s + `DEL` al cambiar en MongoDB |
| Visitas de un partido | `contador:partido:<codigo_partido>:visitas` | String (entero) | 48 h |
| Usuarios conectados | `conectados:partido:<codigo_partido>` | Set | 3 h |
| Encuesta figura del partido | `encuesta:partido:<codigo_partido>:figura` | Sorted Set | sin TTL abierta, 24 h al cerrar |

* **Memoria:** `maxmemory 256mb` con política `volatile-lru`.
* **Persistencia:** AOF + snapshot RDB, como en el laboratorio de clase.
* **Concurrencia:** `INCR`, `ZINCRBY`, `HINCRBY` y `MULTI/EXEC`; nunca
  "leer → modificar → escribir" desde la aplicación.
* **Validez de sesión:** `HGET sesion:<id> usuario_id` devuelve un valor.

---

## 📄 Documentación (sección 8 del enunciado)

| Apartado | Documento |
|---|---|
| Problema de concurrencia | [`docs/patrones_de_acceso.md`](docs/patrones_de_acceso.md) §1 |
| Patrones de acceso | [`docs/patrones_de_acceso.md`](docs/patrones_de_acceso.md) §2 |
| Modelo clave/valor | [`docs/modelo_clave_valor.md`](docs/modelo_clave_valor.md) §1–4 |
| Ciclo de vida | [`docs/ciclo_de_vida_e_invalidacion.md`](docs/ciclo_de_vida_e_invalidacion.md) §1–2 |
| Fuente de verdad y caché | [`docs/ciclo_de_vida_e_invalidacion.md`](docs/ciclo_de_vida_e_invalidacion.md) §3 |
| Concurrencia | [`docs/ciclo_de_vida_e_invalidacion.md`](docs/ciclo_de_vida_e_invalidacion.md) §4 |
| Memoria y escalabilidad | [`docs/memoria_y_escalabilidad.md`](docs/memoria_y_escalabilidad.md) |
| Datos cargados | [`docs/modelo_clave_valor.md`](docs/modelo_clave_valor.md) §5 |
| Operaciones Redis | [`docs/modelo_clave_valor.md`](docs/modelo_clave_valor.md) §6 |
| Pruebas y evidencia | [`docs/evidencia/README.md`](docs/evidencia/README.md) |
| Coherencia con el TPO | [`docs/patrones_de_acceso.md`](docs/patrones_de_acceso.md) §3 |

---

## 📂 Estructura del directorio

```text
fixture2030-redis/
  docker-compose.yml              Servicio Redis, puerto 6379, datos en ~/docker/data/redis
  scripts/
    inicializacion.redis          PING, versión, persistencia y política de memoria
    carga_muestra.redis           Muestra idempotente: 10 sesiones, caché y contadores
    sesiones.redis                Ciclo de vida completo de una sesión
    cache.redis                   Cache-Aside: hit, miss e invalidación
    concurrencia.redis            Contadores, encuesta, ranking y MULTI/EXEC
    metricas.redis                INFO, SCAN y TTL observados
    limpieza.redis                Borrado de las claves del módulo (opcional)
  tools/
    prueba_concurrencia.sh        Clientes redis-cli en paralelo sobre la misma clave
    medicion.sh                   Tiempo de N comandos por operación, con redis-cli
    generar_evidencia.sh          Ejecuta todo en orden y guarda la evidencia
  docs/
    patrones_de_acceso.md         Problema, patrones de acceso y coherencia con el TPO
    modelo_clave_valor.md         Claves, estructuras, datos cargados y scripts
    ciclo_de_vida_e_invalidacion.md  Sesiones, caché, invalidación y concurrencia
    memoria_y_escalabilidad.md    maxmemory, evicción, persistencia y escala
    evidencia/                    Salidas de la corrida y resumen de resultados
```

---

## ⚠️ Alcance del ambiente

Este entorno es **un nodo único de aprendizaje** (standalone). No tiene
réplicas, Sentinel ni Redis Cluster, y no debe presentarse como una topología
de alta disponibilidad. Las diferencias con un despliegue real están en
[`docs/memoria_y_escalabilidad.md`](docs/memoria_y_escalabilidad.md).

Redis corre sin contraseña porque es un ambiente local de desarrollo. Los
scripts no contienen tokens, contraseñas ni datos personales (RNF7).

El `docker-compose.yml` de la raíz del repositorio también incluye este
servicio con el mismo nombre de contenedor y puerto. No levantar los dos al
mismo tiempo.

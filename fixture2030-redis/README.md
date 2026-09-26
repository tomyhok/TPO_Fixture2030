# TPO Fixture 2030 — Módulo de Caché de Usuarios y Sesiones (Redis)

Este directorio contiene la implementación del **Hito 7** utilizando Redis como almacén clave-valor en memoria para manejar sesiones, caché de acceso rápido (Cache-Aside) y contadores concurrentes.

## Requisitos previos

* Docker y Docker Compose instalados.
* Puerto `6379` libre.

No es necesario instalar Redis localmente; todo corre en el contenedor y se utiliza `redis-cli` incluido en el mismo.

## Instrucciones de Ejecución

### 1. Iniciar el entorno

Desde esta carpeta (`fixture2030-redis`), ejecutar:

```bash
docker compose up -d
```
Esto levantará el contenedor `fixture2030-redis` utilizando la imagen `redis:latest` y guardando la persistencia (AOF) en el directorio local `~/docker/data/redis`.

### 2. Verificar el estado del servidor

```bash
docker compose logs -f
```
Verifica que el log indique "Ready to accept connections".

### 3. Abrir el cliente interactivo y ejecutar scripts

Redis no usa SQL, sino comandos directos que pueden ejecutarse de manera interactiva o pasando un archivo.

Para abrir una consola interactiva:
```bash
docker exec -it fixture2030-redis redis-cli
```
Dentro de la consola puedes escribir `PING` y deberías recibir `PONG`.

Para ejecutar los scripts provistos secuencialmente (simulando los flujos de la aplicación):

```bash
docker exec -i fixture2030-redis redis-cli < scripts/inicializacion.redis
docker exec -i fixture2030-redis redis-cli < scripts/carga_muestra.redis
docker exec -i fixture2030-redis redis-cli < scripts/sesiones.redis
docker exec -i fixture2030-redis redis-cli < scripts/cache.redis
docker exec -i fixture2030-redis redis-cli < scripts/concurrencia.redis
docker exec -i fixture2030-redis redis-cli < scripts/metricas.redis
```

*(Las respuestas de los scripts se mostrarán en la salida estándar de tu consola).*

### 4. Detener o reiniciar sin perder datos

Dado que el volumen está mapeado a `~/docker/data/redis` y usamos la bandera `--appendonly yes`, los datos son persistentes a reinicios normales.

Para detener el servicio manteniendo los datos:
```bash
docker compose stop
# o
docker compose down
```

Para reiniciar desde cero y borrar la persistencia (hacerlo con precaución):
```bash
docker compose down
rm -rf ~/docker/data/redis
```

## Arquitectura: Nodo Local vs Producción

El entorno provisto despliega un **único nodo (Standalone)** de Redis. Esto es ideal para desarrollo local y aprendizaje, pero **no es tolerante a fallos**. Si el nodo único se cae, la aplicación pierde acceso a la caché y las sesiones.

En un **despliegue productivo**, se utilizarían topologías que ofrezcan Alta Disponibilidad (HA) y/o escalabilidad horizontal:

*   **Replicación Primario-Secundario (con Sentinel)**: Permite tener copias de lectura y que Sentinel promueva automáticamente a una réplica a primario si el primario falla (failover). La escritura sigue estando limitada a un solo nodo.
*   **Redis Cluster**: Distribuye las claves (sharding lógicamente a través de *hash slots*) entre múltiples nodos primarios, cada uno con sus propias réplicas. Provee escalabilidad masiva tanto de lectura como de escritura, y alta disponibilidad.

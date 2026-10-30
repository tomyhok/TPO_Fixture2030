# Entorno de ejecución

## Servicios

Se usa el `docker-compose.yml` de la raíz del repositorio. Hacen falta solo **Cassandra** y **Redis**:

```bash
# desde la raíz del repo
docker compose up -d cassandra redis
```

Si los contenedores ya existen porque se crearon desde el compose de cada módulo, Docker avisa `container name already in use`. En ese caso se arrancan los existentes, sin borrarlos:

```bash
docker start fixture2030-cassandra fixture2030-redis
```

Verificar:

```bash
docker exec fixture2030-cassandra nodetool status   # debe mostrar UN (Up/Normal)
docker exec fixture2030-redis redis-cli ping        # PONG
```

Cassandra tarda ~1 minuto en aceptar conexiones después de arrancar.

## Configuración usada en las mediciones

| Componente | Versión / configuración |
|---|---|
| Cassandra | 5.0.9, 1 nodo, `MAX_HEAP_SIZE=2G`, keyspace `fixture2030_carga` con `SimpleStrategy` RF = 1 |
| Redis | 8.10.2, `maxmemory 256mb`, `maxmemory-policy volatile-lru` en el contenedor activo durante la medición (`noeviction` en el `docker-compose.yml` unificado tras las correcciones del Hito 7), AOF activado |
| Drivers | `cassandra-driver` 3.30.1, `redis` 8.1.0 (`requirements.txt`) |
| Python | 3.14.5 |
| Host | Mac, macOS 26.6 (Darwin 25.6.0), 8 CPUs, 16 GB RAM. Docker Desktop con 8 CPUs y 7,6 GB |

Las versiones exactas de cada corrida quedan en el campo `entorno` de cada `docs/evidencia/resultados/*.json`.

## Conexión y secretos

Cassandra y Redis del laboratorio no tienen usuario ni contraseña. Los hosts y puertos se leen de variables de entorno con valores por defecto `127.0.0.1:9042` y `127.0.0.1:6379`; hay un ejemplo en `config/configuracion-ejemplo.env`. Si hiciera falta un `.env` real, va en `config/.env`, que está en `.gitignore`.

## Control de recursos (RNF9)

- El generador usa como máximo `--procesos` núcleos (3 por defecto, de 8).
- Cassandra queda limitada por su heap de 2 GB y Redis por `maxmemory 256mb`. Las claves del muro están acotadas con `LTRIM 0 99` y tienen `TTL 60s` (bajo `volatile-lru` pueden ser desalojadas; bajo `noeviction` expiran por TTL y ocupan < 2 MiB en total para 64 partidos).
- Cada corrida dura 150 s y se puede cortar con Ctrl+C sin perder los resultados ya medidos.
- `docker stats` se registra cada ~5 s durante la corrida (`recursos_docker` en el JSON).

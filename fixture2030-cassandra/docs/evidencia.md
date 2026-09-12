# Evidencia de Ejecución — Hito 6 (Cassandra)

Registro exigido por RF13 y RNF9.

> **Estado:** completado con una corrida real del **11/09/2026** sobre la
> notebook de referencia descrita en la sección 1. Los únicos campos pendientes
> son el nombre del integrante que ejecuta y las capturas de pantalla.
>
> Cada integrante que reproduzca el hito en otra máquina debe **volver a
> completar este documento con sus propios números**: el enunciado prohíbe
> declarar tasas de escritura sin indicar método, entorno y resultado observado,
> y la etiqueta `cassandra:latest` puede traer otra versión.

---

## 1. Ambiente de prueba

| Dato | Valor | Cómo obtenerlo |
|---|---|---|
| Fecha y hora de ejecución | 2026-09-11, 23:40–23:58 (UTC−3) | — |
| Integrante que ejecuta | _(completar)_ | — |
| Versión de Cassandra | **5.0.9** (cqlsh 6.2.0, CQL spec 3.4.7, protocolo nativo v5) | `cqlsh -e "SHOW VERSION"` |
| Imagen y digest | `cassandra@sha256:da9dad3aaf67c4e5126c6aafa769460d75f27c1716951c48896ff5c4e97d2af3` | `docker image inspect cassandra:latest --format '{{index .RepoDigests 0}}'` |
| Versión de Docker | 27.5.1 (build 9f9e405) | `docker --version` |
| Sistema operativo | macOS 26.6.2 | — |
| CPU (modelo y núcleos) | Apple M1 Pro, 8 núcleos | — |
| RAM total / RAM asignada a Docker | 16 GB / 7,7 GB | Docker Desktop → Settings → Resources |
| Almacenamiento | SSD NVMe interno (bind mount de Docker Desktop) | SSD NVMe / SSD SATA / HDD |

> El enunciado exige usar `cassandra:latest`. Como esa etiqueta cambia con el
> tiempo, registrar la versión observada es lo que permite explicar diferencias
> de comportamiento entre corridas (nota 5 del enunciado).

## 2. Creación del esquema

```
docker compose exec cassandra cqlsh -f /scripts/01-keyspace.cql
docker compose exec cassandra cqlsh -f /scripts/02-tablas.cql
```

| Verificación | Resultado esperado | Resultado observado |
|---|---|---|
| `DESCRIBE KEYSPACE fixture2030` | keyspace con RF=1 | OK — `SimpleStrategy`, `replication_factor: '1'`, `durable_writes: true` |
| `DESCRIBE TABLES` | 4 tablas | OK — `comentarios_por_partido`, `comentarios_por_usuario`, `comentarios_en_revision`, `metricas_comentario` |
| `nodetool status` | 1 nodo en estado `UN` | OK — `UN 172.25.0.2`, 16 tokens, 100 % owns, rack1 |

_Captura de pantalla:_ `capturas/01-esquema.png`

## 3. Carga de muestra

```
docker compose exec cassandra cqlsh -f /scripts/03-carga-muestra.cql
```

| Verificación | Esperado | Observado |
|---|---|---|
| `comentarios_por_partido` | 35 filas | 35 |
| `comentarios_por_usuario` | 35 filas | 35 |
| `comentarios_en_revision` | 5 filas | 5 |
| Reejecución del script (idempotencia, RNF7) | mismos conteos | 35 / 35 / 5 — sin duplicados |

_Captura:_ `capturas/02-carga-muestra.png`

## 4. CRUD y consultas

| Script | Qué se verifica | Observado |
|---|---|---|
| `04-crud.cql` | Insert en batch, lectura puntual, updates, LWT aplicada (`[applied] = True`), counters, deletes y conteo final en 0 | OK — LWT devolvió `[applied] = True`; counters `likes=1, respuestas=1`; conteo final `0` |
| `05-consultas.cql` | Q1 devuelve orden descendente; Q2 devuelve el historial; Q3 devuelve solo pendientes; Q4 devuelve los counters | OK — las cinco consultas devolvieron filas en el orden esperado; el `TTL` de la cola de moderación se leyó en 604.786 s |

_Capturas:_ `capturas/03-crud.png`, `capturas/04-consultas.png`

## 5. Carga masiva

```
bash tools/carga_masiva.sh 1000000
```

| Dato | Valor |
|---|---|
| Filas generadas (comentarios) | 1.000.000 |
| Filas escritas en total (2 tablas + cola) | 2.079.974 (1.000.000 + 1.000.000 + 79.974) |
| Semilla del generador | `2030` |
| Tiempo de generación de los CSV | 14,6 s (68.709 filas/s) |
| Tiempo de carga con `COPY` | 20,2 s para `comentarios_por_partido` (1.000.000 de filas) |
| **Tasa de escritura observada** | **49.490 filas/s** en el `COPY` de la tabla principal |
| Parámetros `COPY` usados | `INGESTRATE=50000`, `NUMPROCESSES=4`, `CHUNKSIZE=5000`, `MAXBATCHSIZE=20` |
| Errores o reintentos | 0 filas omitidas (`0 skipped`) |

_Captura:_ `capturas/05-carga-masiva.png`

## 6. Distribución entre particiones

```
docker compose exec cassandra cqlsh --request-timeout=600 -f /scripts/06-medicion.cql
```

| Métrica | Valor observado |
|---|---|
| Total de filas en `comentarios_por_partido` | 1.000.035 (`COUNT(*)` completo falla por timeout; ver nota abajo) |
| Filas por shard en la ventana medida (0/1/2/3) | P-002 / 203006160120 → **155 / 152 / 142 / 140** |
| Desvío máximo entre shards | **+5,3 %** sobre la media de 147,25 filas |
| Tamaño máximo de partición (`Compacted partition maximum bytes`) | 20.501 bytes (≈ 20 KB) |
| Celdas vivas promedio por slice | 103,0 |
| Tombstones promedio por slice | 1,0 |

Fuente de las tres últimas filas:

```
docker compose exec cassandra nodetool tablestats fixture2030.comentarios_por_partido
docker compose exec cassandra nodetool tablehistograms fixture2030 comentarios_por_partido
```

_Captura:_ `capturas/06-distribucion.png`

## 7. Costo comparado de las consultas (tracing)

| Consulta | Particiones tocadas | Tiempo total (µs) | Observaciones |
|---|---|---|---|
| Q1 con clave de partición | **1** (`Executing single-partition query` una sola vez) | **2.116 µs** | 20 filas vivas, 0 tombstones |
| Índice secundario sin clave de partición | **17 rangos** + ~14 particiones (`Submitting range requests on 17 ranges`) | **17.035 µs** | Mismo `LIMIT 20`, **8× más lento** |

_Captura:_ `capturas/07-tracing.png`

## 8. Prueba de escritura sostenida

```
bash tools/benchmark_escritura.sh 500000 32
```

| Dato | Valor |
|---|---|
| Operaciones ejecutadas (`n`) | 300.000 |
| Hilos (`threads`) | 64 |
| Nivel de consistencia | `ONE` |
| **Op rate (op/s)** | **14.757 op/s** (16.722 filas/s) |
| Latencia media | 2,7 ms (mediana 1,6 ms) |
| Latencia percentil 99 | 17,1 ms (p95: 8,1 ms; p99,9: 81,1 ms) |
| Latencia máxima | 217,4 ms |
| Errores totales | 0 |

_Captura:_ `capturas/08-stress.png`

### Interpretación

**El objetivo de 10.000 escrituras/s del RF12 se alcanzó y se superó:**
14.757 op/s sostenidas con 64 hilos, sin errores, contra la tabla real del
módulo y con su misma clave de partición. La latencia mediana se mantuvo en
1,6 ms y el percentil 99 en 17,1 ms.

El pico de 217,4 ms en la latencia máxima coincide con las 6 pausas de
recolección de basura registradas por la corrida (0,6 s de GC en total sobre un
heap de 2 GB). Ese es el primer recurso que limita esta prueba: subir
`MAX_HEAP_SIZE` reduciría la cola de latencia. El segundo límite es que el
cliente `cassandra-stress` corre dentro del mismo contenedor y compite por los
mismos 8 núcleos que el servidor, de modo que el número reportado es una **cota
inferior** de lo que daría el nodo con un cliente externo.

La carga por `COPY` alcanzó 49.490 filas/s, una cifra más alta porque escribe
en lotes `UNLOGGED` de 20 filas por partición, mientras que `cassandra-stress`
mide escrituras individuales, que es el patrón real de la aplicación.

**Sobre la distribución:** los 4 shards de la ventana medida quedaron en
155/152/142/140 filas, con un desvío máximo de +5,3 % sobre la media. El hash
`crc32(id_usuario) % 4` reparte de forma pareja, que era exactamente el objetivo
de la defensa anti-hotspot. El tamaño máximo de partición observado
(20.501 bytes) está muy por debajo del umbral de alerta de 100 MB declarado en
el análisis, porque el dataset de 1.000.000 de filas distribuido entre
~313.000 particiones da un promedio bajo; con los supuestos de un partido
popular real la partición pico proyectada es de ~15,7 MB, igualmente holgada.

**Sobre el `COUNT(*)` completo:** falló con `ReadFailure` y `ReadTimeout` sobre
1.000.000 de filas mientras había escrituras en curso. No es un defecto del
modelo: es la demostración práctica de por qué Cassandra no resuelve
agregaciones globales y de por qué toda consulta de la aplicación se acota por
clave de partición. La estimación de `nodetool tablestats`
(313.512 particiones, 191 MB vivos) sí responde de inmediato, porque no recorre
los datos.

### Limitaciones del ambiente

- Nodo único: no hay paralelismo entre réplicas ni coordinación distribuida real.
- `RF=1` y `CL=ONE`: no se mide el costo de un quórum.
- Cliente y servidor comparten CPU dentro del mismo contenedor.
- Heap de la JVM limitado a 2 GB por el Compose.
- Bind mount de Docker Desktop: en macOS y Windows agrega virtualización de E/S.

**Estas limitaciones deben acompañar cualquier número reportado.** El enunciado
prohíbe declarar tasas de escritura sin indicar método, entorno y resultado
observado.

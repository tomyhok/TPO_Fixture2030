# Integridad y limitaciones

## 1. Validación de integridad

`scripts/validar_integridad.py` corre después de cada prueba (los wrappers `.sh` lo llaman solos). Toma el CSV con **todas** las escrituras intentadas y no da por bueno nada por el solo hecho de que el driver no haya tirado excepción:

| Control | Cómo se verifica |
|---|---|
| Generados vs aceptados vs rechazados | Estado de cada escritura en el CSV del cliente |
| Ids únicos | `id_comentario` repetidos en el CSV |
| Aceptado = presente en las 2 tablas | Lectura por clave primaria completa en `comentarios_por_partido` y `comentarios_por_usuario` |
| Sin escrituras parciales | Los rechazados no deben estar en ninguna tabla |
| Sin duplicados ni pérdidas por partición | `COUNT(*)` de cada partición `(partido, ventana, shard)` tocada = cantidad esperada según el CSV |
| Muro de Redis (optimizado) | Sin duplicados. Cada id del muro existe en Cassandra. Frescura: cuántos de los últimos comentarios aceptados todavía no aparecen en el muro |

Si una consulta de la propia validación da timeout, se reintenta. Un error de lectura del validador no es un dato perdido. En una versión anterior esto daba **falsos faltantes** (71 y 130 en una corrida de 232 742 escrituras): los conteos por partición coincidían, pero algunas consultas puntuales vencían.

### Resultados

| Corrida | Escrituras generadas | Aceptadas | Rechazadas | Faltantes (partido / usuario) | Parciales | Particiones controladas | Particiones con diferencias | Resultado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `base_20261029-211153` (capacidad) | 14 592 | 14 592 | 0 | 0 / 0 | 0 | 767 | 0 | OK |
| `optimizado_20261029-211547` (capacidad) | 207 936 | 207 936 | 0 | 0 / 0 | 0 | 768 | 0 | OK |
| `base_20261029-212119` (500 ops/s) | 13 575 | 13 575 | 0 | 0 / 0 | 0 | 847 | 0 | OK |
| `optimizado_20261029-212501` (500 ops/s) | 13 620 | 13 620 | 0 | 0 / 0 | 0 | 821 | 0 | OK |
| `base_20261029-212927` (capacidad, repetición) | 25 804 | 25 804 | 0 | 0 / 0 | 0 | 954 | 0 | OK |
| `base_20261029-213317` (capacidad, 6 procesos) | 34 166 | 34 166 | 0 | 0 / 0 | 0 | 1024 | 0 | OK |

Muros de Redis, validados inmediatamente después de cada corrida:

| Corrida | Muros | Elementos | Duplicados | Ids inexistentes en Cassandra | Últimos comentarios reales ausentes del muro |
|---|---:|---:|---:|---:|---:|
| `optimizado_20261029-211547` | 64 | 6 400 | 0 | 0 | 0 |
| `optimizado_20261029-212501` | 64 | 6 292 | 0 | 0 | 2 (1 en P-001) |

Los 2 ausentes no son una pérdida, porque esos comentarios están en Cassandra. Muestran la **consistencia eventual** del muro, que se explica en [hipotesis_y_optimizacion.md](hipotesis_y_optimizacion.md#trade-offs): si un comentario se escribe mientras el muro se está reconstruyendo, no aparece en el muro hasta la próxima reconstrucción (como máximo 60 s, por el TTL).

Preparación (`preparacion.json`): 100 000 generados, 0 errores, `COUNT(*)` = 100 000 en las dos tablas.

## 2. Limitaciones

### Del entorno

- **Un solo nodo de Cassandra con RF = 1.** No hay replicación, quórum ni tráfico entre nodos, así que las latencias de escritura reales serían mayores.
- **Todo corre en la misma notebook.** Generador, Cassandra y Redis comparten 8 CPUs, y la red es loopback o la red interna de Docker Desktop. Las latencias no incluyen la red de un despliegue real.
- **Los recursos se miden con `docker stats` cada ~5 s.** Es una muestra gruesa: no captura picos cortos.
- **Variabilidad entre corridas.** Las métricas de una misma configuración cambian entre ejecuciones (ver [hipotesis_y_optimizacion.md](hipotesis_y_optimizacion.md)). Hay pocas repeticiones, así que las diferencias chicas no son concluyentes. Las de un orden de magnitud sí.

### Del generador

- **Cliente en Python.** El driver de Cassandra procesa las respuestas en un hilo por proceso, y el GIL limita cada proceso a un núcleo. Por eso la carga se reparte en procesos y se registra la CPU del generador. En la línea base el cliente gasta CPU procesando 12 respuestas por lectura, así que parte de la latencia que se mide es del cliente y no de Cassandra.
- **Lazo cerrado en la prueba de capacidad.** La cantidad de operaciones depende de la latencia, por eso se agregó la variante de carga fija (500 ops/s) para comparar en igualdad de condiciones.
- **Las lecturas no validan el contenido.** Se mide que el muro responda, no que el texto mostrado sea el correcto. La correspondencia entre Redis y Cassandra se controla aparte, en la validación.

### De lo que se puede concluir

- **No se probó el volumen del torneo.** Las corridas escriben entre 13 000 y 208 000 comentarios sobre una base de 100 000. La proyección del Mundial (millones de comentarios y miles de escrituras por segundo en varios partidos) es una **estimación**, no una medición.
- El resultado vale para **este** patrón: muchas lecturas sobre una clave caliente. Con un muro poco leído o un historial por usuario, la ganancia de Redis sería mucho menor.
- La alternativa relacional y el Data Mart son **análisis conceptuales**: no se midieron.

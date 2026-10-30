# Línea base

Muro leído directamente de Cassandra (12 consultas por lectura). El escenario está en [flujo_y_escenario_de_carga.md](flujo_y_escenario_de_carga.md).

## 1. Configuración registrada

| Dato | Valor |
|---|---|
| Fecha | 2026-10-29, entre 21:11 y 21:36 (hora local) |
| Código | commit `17b3693` + scripts de este hito sin commitear; `sha1_scripts` (hash de `scripts/*.py`, guardado en cada JSON) = `748e059934f1` en las 4 corridas principales y `651884c7e882` en las 2 de la prueba de hipótesis. La única diferencia es que se agregó la captura de `nodetool proxyhistograms` al final; la carga es la misma |
| Cassandra | 5.0.9, 1 nodo, heap 2 GB, keyspace `fixture2030_carga` RF = 1, timeout del cliente 2 s |
| Redis | 8.10.2 (no se usa en la línea base) |
| Cliente | Python 3.14.5, cassandra-driver 3.30.1, 50 usuarios virtuales en 3 procesos |
| Host | macOS 26.6, 8 CPUs, 16 GB. Docker Desktop: 8 CPUs, 7,6 GB |
| Datos | 100 000 comentarios previos (50 477 de P-001) + lo escrito por cada corrida |
| Duración | 30 s de rampa (no se miden) + 120 s de sostenimiento |

## 2. Resultados medidos

Latencias en **milisegundos**, medidas por el cliente (`time.perf_counter`) desde que arranca la operación hasta que tiene la respuesta completa. Solo cuentan las operaciones sin error del período de sostenimiento.

| Métrica | Capacidad (sin pausa) — `base_20261029-211153` | Capacidad, repetición — `base_20261029-212927` | Carga fija 500 ops/s — `base_20261029-212119` |
|---|---:|---:|---:|
| Operaciones medidas | 58 140 | 98 275 | 59 762 |
| Throughput (ops/s) | 484,5 | 819,0 | 498,0 |
| Errores | 0 | 0 | 0 |
| Lectura min / p50 / p95 / p99 / max | 5,06 / 72,35 / 157,95 / 249,35 / 542,64 | 2,33 / 9,78 / 31,78 / 57,57 / 221,25 | 2,11 / 14,70 / 31,78 / 58,83 / 181,86 |
| Escritura p50 / p95 / p99 / max | 69,74 / 159,12 / 245,91 / 521,13 | 6,91 / 26,16 / 53,96 / 206,02 | 11,70 / 29,40 / 54,45 / 166,46 |
| CPU Cassandra (promedio `docker stats`, % de 1 núcleo) | 122 % | 129 % | 77 % |
| CPU Redis | 1 % | 0,2 % | 0,2 % |
| CPU del generador (% de 1 núcleo, 3 procesos) | 140 % | 192 % | 100 % |
| Escrituras generadas / aceptadas / rechazadas | 14 592 / 14 592 / 0 | 25 804 / 25 804 / 0 | 13 575 / 13 575 / 0 |
| Integridad | OK | OK | OK |

La serie de operaciones por segundo (`ops_por_segundo`) también está en cada JSON.

## 3. Observaciones de estabilidad

- **Hay mucha variabilidad entre corridas con la misma configuración.** La capacidad dio 484 y 819 ops/s, y el p50 de lectura, 72 y 10 ms. En la primera corrida el throughput por segundo osciló entre 195 y 747 ops/s, lo que sugiere pausas del lado del servidor. Una posible causa, **no verificada**, es la compactación o el flush de Cassandra después de una corrida de prueba previa (descartada, no forma parte de la evidencia) que había escrito ~230 000 comentarios. Con dos corridas no alcanza para una conclusión estadística. Por eso la comparación principal se hace con la carga fija, que fue estable (428–533 ops/s por segundo).
- **0 errores y 0 timeouts** en todas las corridas: con esta carga el sistema se degrada en latencia, no en errores.
- **Los promedios esconden las colas.** En carga fija, la lectura tiene p50 de 14,7 ms pero p99 de 58,8 ms y máximo de 182 ms.

La interpretación (dónde se va el tiempo) está en [hipotesis_y_optimizacion.md](hipotesis_y_optimizacion.md).

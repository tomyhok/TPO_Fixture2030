# Comparacion linea base vs optimizado

| Metrica | Linea base | Optimizado | Variacion |
|---|---:|---:|---:|
| Throughput (ops/s) | 498.0 | 500.0 | +0.4% |
| Operaciones en sostenimiento | 59762 | 60000 | +0.4% |
| Errores | 0 | 0 | - |
| Latencia lectura p50 (ms) | 14.7 | 1.67 | -88.6% |
| Latencia lectura p95 (ms) | 31.78 | 11.1 | -65.1% |
| Latencia lectura p99 (ms) | 58.83 | 17.57 | -70.1% |
| Latencia lectura max (ms) | 181.86 | 77.02 | -57.6% |
| Latencia escritura p50 (ms) | 11.7 | 5.63 | -51.9% |
| Latencia escritura p95 (ms) | 29.4 | 16.15 | -45.1% |
| Latencia escritura p99 (ms) | 54.45 | 22.02 | -59.6% |
| Latencia escritura max (ms) | 166.46 | 76.09 | -54.3% |
| CPU del generador (%) | 100.0 | 38.9 | -61.1% |

- Linea base: `docs/evidencia/resultados/base_20261029-212119.json` (2026-10-29T21:21:19, commit 17b3693 (con cambios sin commitear))
- Optimizado: `docs/evidencia/resultados/optimizado_20261029-212501.json` (2026-10-29T21:25:01, commit 17b3693 (con cambios sin commitear))
- Cache optimizado: 47727 hits / 168 misses

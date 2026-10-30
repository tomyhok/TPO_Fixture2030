# Comparacion linea base vs optimizado

| Metrica | Linea base | Optimizado | Variacion |
|---|---:|---:|---:|
| Throughput (ops/s) | 484.5 | 6737.3 | +1290.6% |
| Operaciones en sostenimiento | 58140 | 808479 | +1290.6% |
| Errores | 0 | 0 | - |
| Latencia lectura p50 (ms) | 72.35 | 0.98 | -98.6% |
| Latencia lectura p95 (ms) | 157.95 | 3.86 | -97.6% |
| Latencia lectura p99 (ms) | 249.35 | 9.36 | -96.2% |
| Latencia lectura max (ms) | 542.64 | 95.46 | -82.4% |
| Latencia escritura p50 (ms) | 69.74 | 3.35 | -95.2% |
| Latencia escritura p95 (ms) | 159.12 | 8.76 | -94.5% |
| Latencia escritura p99 (ms) | 245.91 | 18.93 | -92.3% |
| Latencia escritura max (ms) | 521.13 | 617.76 | +18.5% |
| CPU del generador (%) | 139.5 | 200.4 | +43.7% |

- Linea base: `docs/evidencia/resultados/base_20261029-211153.json` (2026-10-29T21:11:53, commit 17b3693 (con cambios sin commitear))
- Optimizado: `docs/evidencia/resultados/optimizado_20261029-211547.json` (2026-10-29T21:15:46, commit 17b3693 (con cambios sin commitear))
- Cache optimizado: 646670 hits / 173 misses

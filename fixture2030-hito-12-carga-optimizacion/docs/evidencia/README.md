# Evidencia

Todas las cifras son **mediciones reales** de las corridas del 2026-10-29. No hay capturas de pantalla: la evidencia está en texto, en los archivos que generan los scripts.

| Archivo | Qué es |
|---|---|
| `resultados/preparacion.json` | Carga inicial: generados vs contados |
| `resultados/<modo>_<fecha>.json` | Métricas de la corrida, configuración, entorno (versiones, `sha1_scripts`), `docker stats`, ops por segundo y, en las últimas dos, `nodetool proxyhistograms` |
| `resultados/<modo>_<fecha>_escrituras.csv.gz` | Cada comentario intentado (id, partición, estado): entrada de la validación |
| `resultados/<modo>_<fecha>_integridad.json` | Resultado de `validar_integridad.py` |
| `comparacion_carga_fija.md` | Línea base contra optimizado con 500 ops/s (comparación principal) |
| `comparacion_capacidad.md` | Línea base contra optimizado sin pausa |
| `ejecucion_completa.log` | Salida de `scripts/ejecutar_todo.sh` (4 corridas) |
| `ejecucion_hipotesis_cliente.log` | Salida de `scripts/ejecutar_hipotesis_cliente.sh` (línea base con 3 y 6 procesos) |

| Corrida | Modo | Variante |
|---|---|---|
| `base_20261029-211153` | base | capacidad, 3 procesos |
| `optimizado_20261029-211547` | optimizado | capacidad, 3 procesos |
| `base_20261029-212119` | base | 500 ops/s |
| `optimizado_20261029-212501` | optimizado | 500 ops/s |
| `base_20261029-212927` | base | capacidad, 3 procesos (repetición) |
| `base_20261029-213317` | base | capacidad, 6 procesos |

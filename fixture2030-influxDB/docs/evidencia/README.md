# Evidencia de ejecución (Hito 8)

Toda la evidencia se generó con `bash tools/generar_evidencia.sh 10000000`, que corre los scripts en el orden del README y guarda la salida de cada uno en esta carpeta.

## Ambiente

| Dato | Valor |
| :--- | :--- |
| Fecha de ejecución | 2026-10-07 |
| Versión de InfluxDB | InfluxDB 3 Core 3.12.0 (imagen `influxdb:3-core`) |
| Equipo | Apple M1 Pro, 8 núcleos, 16 GB de RAM (macOS) |
| Recursos de Docker | 8 CPUs, ~8 GB de RAM |
| Punto de partida | Directorio `~/docker/data/influxdb` vacío y base recién creada |

## Resultados

| Paso | Archivo | Resultado observado |
| :--- | :--- | :--- |
| Ambiente | `00_ambiente.txt` | Versión, imagen y recursos del equipo. |
| Inicialización | `01_inicializacion.txt` | Token creado (guardado fuera del repo) y base `fixture2030` con retención de 30 días. |
| Generación | `02_generacion.txt` | 9.999.980 puntos (254 series × 39.370 puntos) en 17,3 s. Archivo de 1,35 GB. |
| Carga | `03_carga.txt` | 9.999.980 líneas en 139 requests, ~24,7 s de escritura (~405.000 puntos/s). 35,8 s en total contando el `docker cp` del archivo. |
| Consultas | `04_consultas_temporales.txt` | Ventana de 10 minutos y comparación de los dos equipos de M001: 0,57 s. |
| Agregaciones | `05_agregaciones.txt` | Resumen por equipo y agregación por minuto: 0,41 s. |
| Validación | `06_validacion.txt` | 9.999.980 puntos, 127 partidos, 254 series, 39.370 puntos en cada serie (coincide con la estrategia). Tardó 69 s. |
| Persistencia | `07_persistencia.txt` | Después de `docker restart` siguen los 9.999.980 puntos. ~521 MB en disco. |

Los tiempos son de un solo script completo (incluyen arrancar `docker exec` y el CLI), medidos con el reloj del sistema.

## Interpretación

*   **Carga:** el objetivo de 10M+ puntos se alcanzó en esta notebook. Los datos generados (1,35 GB de texto) quedan en ~521 MB en disco gracias a la compresión en Parquet.
*   **Consultas acotadas vs. no acotadas:** las consultas que filtran por `partido_id` y rango de tiempo responden en menos de un segundo. La validación, que recorre los 10M de puntos sin filtro de tiempo (`COUNT DISTINCT`), tardó 69 s. Por eso todas las consultas de operación acotan tiempo y dimensiones (RNF8).
*   **Interpretación de M001:** en la ventana de 10 minutos ambos equipos tienen 599 puntos (uno por segundo). La agregación por minuto muestra cómo baja la audiencia (`pico_usuarios`) y cómo los tiros acumulados solo crecen, que es lo esperado para un contador.

## Limitaciones

*   Los datos son simulados (`generacion_puntos.py`), no vienen de un proveedor real.
*   Es una sola instancia local: no se probó escritura concurrente desde varias fuentes ni la retención en acción (los timestamps son de 2030, así que todavía no vencen).
*   Con 10M de puntos cada serie cubre ~11 horas, más que un partido real. Se eligió así para llegar al volumen objetivo con la misma cantidad de series.

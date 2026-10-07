# Cardinalidad y Escalabilidad (Hito 8)

El objetivo propuesto para este módulo era soportar **10M+ puntos** conservando consultas rápidas. Un factor crítico para InfluxDB es el control de la cardinalidad de la base de datos (la cantidad de series temporales únicas en memoria e índice).

## Estimación Matemática de Cardinalidad

La cardinalidad máxima teórica en este modelo se calcula multiplicando los valores posibles de cada Tag:
*   `partido_id`: 127 partidos (según reglamento del Mundial con 48 equipos).
*   `equipo_id`: 48 equipos (pero solo 2 equipos juegan un partido a la vez).

**Cálculo real de combinaciones:** 
127 partidos × 2 equipos por partido = **254 series únicas**.

Esta cardinalidad de 254 es **excelente y extremadamente baja**. Mantiene el índice de memoria invertida pequeño, previniendo cuellos de botella de OOM (Out Of Memory) y permitiendo que InfluxDB agrupe las medidas de forma contigua en el almacenamiento.

## Estrategia de Carga (10M+ Puntos)

La carga está separada en tres pasos: generación (`generacion_puntos.py`), carga (`carga_lotes.sh`) y validación (`validacion.sh`).

*   **Generación de timestamps:** cada serie arranca en el inicio de su partido y avanza de a 1 segundo. La precisión es de segundos y se declara en el generador y en la carga (`--precision s`).
*   **Orden:** el archivo se escribe ordenado por serie y por tiempo. InfluxDB acepta igual datos desordenados o tardíos porque cada punto trae su timestamp.
*   **Tamaño de lote:** el CLI de InfluxDB parte el archivo en lotes de 10 MiB (con 10M de puntos fueron 139 requests de ~72.000 líneas).
*   **Concurrencia:** hasta 8 requests en paralelo (`--max-concurrent-requests 8`) y compresión `--gzip`.
*   **Errores y reintentos:** si un lote falla, el CLI corta con error y el script se detiene (`set -e`). Como un punto con la misma serie y timestamp reemplaza al anterior, se puede volver a correr la carga completa sin duplicar datos.
*   **Validación:** `validacion.sh` comprueba el total de puntos, la cantidad de partidos y series, y que todas las series tengan la misma cantidad de puntos.

## Prueba realizada vs. objetivo

En esta notebook (Apple M1 Pro, 16 GB) se cargaron **9.999.980 puntos** en ~25 s de escritura (~405.000 puntos/s). El detalle está en [`evidencia/README.md`](evidencia/README.md).

Límites observados del laboratorio:
*   El archivo de 10M de puntos ocupa 1,35 GB; para volúmenes mucho mayores conviene generar y cargar por partes en vez de un único archivo.
*   Las consultas sin rango de tiempo sobre los 10M de puntos tardan más de un minuto (la validación tardó 69 s), mientras que las acotadas responden en menos de un segundo.

Qué cambiaría con más carga o más fuentes:
*   Con muchas fuentes escribiendo a la vez, cada estadio enviaría sus propios lotes en paralelo en vez de un único archivo.
*   La cardinalidad no crece con el volumen: más puntos por serie no agregan series. Solo crecería si se agregan tags (por ejemplo `jugador_id`).
*   Para producción haría falta separar escritura y consulta en distintos nodos (InfluxDB 3 Enterprise) y monitorear la instancia, algo que queda fuera del alcance de este hito.

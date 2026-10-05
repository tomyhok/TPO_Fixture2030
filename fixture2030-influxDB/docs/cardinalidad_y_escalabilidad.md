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

Para lograr el volumen requerido sin saturar el entorno local:
1.  **Batching:** La inyección no se realiza punto a punto (API simple), sino que se genera un archivo *Line Protocol* masivo y se inyecta por el CLI de InfluxDB (`influxdb3 write`).
2.  **Límites CLI:** Se configuran parámetros internos concurrentes (`--max-concurrent-requests 8` y compresión `--gzip`) que permiten que el propio cliente parta el archivo y maximice el I/O sin ahorcar el contenedor.
3.  **Generación Realista:** El script de Python simula la carga distribuyendo los puntos entre los 127 partidos con una variación estadística natural en lugar de enviar un pico masivo a una sola serie.

El script `generacion_puntos.py` fue validado en este entorno generando eficientemente el archivo de prueba y el archivo masivo.

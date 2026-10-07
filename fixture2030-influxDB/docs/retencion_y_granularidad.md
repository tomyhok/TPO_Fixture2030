# Retención, Granularidad y Ciclo de Vida (Hito 8)

La resolución de 1 segundo solo es necesaria mientras se juega el partido y en los días siguientes. Después, las preguntas del torneo (resumen por partido, evolución por minuto, picos de audiencia) se responden con datos agregados. Conservar todo a 1 segundo para siempre ocuparía disco sin responder preguntas nuevas.

## 1. Ciclo de vida

| Etapa | Granularidad | Dónde | Cuánto se conserva | Para qué |
| :--- | :--- | :--- | :--- | :--- |
| En vivo | 1 s (original) | base `fixture2030` | 30 días (`--retention-period 30d`, creado en `inicializacion.sh`) | Pantalla en vivo, comparación entre equipos, revisión posterior del partido (patrones 1 y 2). |
| Histórico | 1 minuto | base `fixture2030_historico` (propuesta) | Sin vencimiento | Evolución de cada partido y comparación entre partidos y torneos. |
| Resumen | 1 fila por equipo y partido | misma base histórica (propuesta) | Sin vencimiento | Ficha del partido y estadísticas del torneo (patrón 3). |

**Por qué 30 días:** el dato de 1 segundo se consulta sobre todo durante el partido y en los días siguientes (repeticiones, revisión de jugadas). Treinta días dan margen de sobra para eso y para volver a calcular los resúmenes si un proceso de downsampling falla. Con 48 equipos el torneo dura más de 30 días (unas 5–6 semanas), así que los partidos de la primera fecha pierden el detalle de 1 segundo antes de la final. Eso es intencional: para entonces esos partidos ya tienen su versión por minuto y su resumen en la base histórica.

InfluxDB borra los datos vencidos comparando el timestamp de cada punto con la hora actual. No hace falta ningún proceso de limpieza.

## 2. Downsampling (propuesto, no implementado)

Una tarea programada, por ejemplo una vez por día, leería el día anterior de `fixture2030`, lo agregaría por minuto con `date_bin(INTERVAL '1 minute', time)` y escribiría el resultado en `fixture2030_historico`. La consulta 2 de `agregaciones.sh` es justamente esa agregación, ejecutada sobre un partido. En este hito no se implementó la tarea ni se creó la base histórica.

**Efecto sobre el almacenamiento:** pasar de 1 punto por segundo a 1 por minuto reduce las filas 60 veces. Con el volumen medido en el laboratorio (~52 bytes por fila en disco), el torneo real (≈1,5M filas a 1 s) ocupa unos 80 MB en crudo y ≈1,3 MB por minuto.

## 3. Agregación según la semántica de cada medida

| Medida | Agregado por minuto | Resumen por partido | Por qué |
| :--- | :--- | :--- | :--- |
| `posesion_pct` | `AVG` | `AVG` | Es una muestra de un valor instantáneo: lo representativo es el promedio. |
| `pases_completados` | `MAX` (acumulado al final del minuto) | `MAX` (total del partido) | Es un contador que nunca baja. La cantidad ocurrida dentro del minuto se obtiene como `MAX - MIN`. |
| `tiros` | `MAX` | `MAX` | Igual que los pases. |
| `usuarios_activos` | `MAX` (pico del minuto) | `MAX` (pico del partido) | Para dimensionar la plataforma interesa el pico, no el promedio. |

## 4. Impacto de la política

*   **Consultas en vivo:** no se ven afectadas, porque el partido en curso siempre está dentro de los 30 días con su resolución original.
*   **Análisis histórico:** después de 30 días ya no se puede ver lo que pasó segundo a segundo, solo minuto a minuto. Esa es la pérdida que se acepta a cambio del ahorro de espacio.
*   **Almacenamiento y costo:** el volumen de 1 segundo queda acotado a los últimos 30 días y el histórico crece 60 veces más despacio.

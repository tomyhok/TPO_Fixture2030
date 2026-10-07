# Retención, Granularidad y Ciclo de Vida (Hito 8)

El modelo de InfluxDB maneja el almacenamiento histórico, y los datos no deben persistir eternamente con resolución microscópica, dado que incurrirían en costos de disco innecesarios para análisis que solo requieren visualizaciones de tendencia a largo plazo.

## 1. Retención (Data Lifecycle)
Durante la inicialización (ver `inicializacion.sh`), la base de datos `fixture2030` se instanció intencionalmente con la bandera `--retention-period 30d`.
*   **Justificación:** El torneo del mundial dura exactamente un mes (desde fase de grupos hasta la final). Conservar datos puros de un segundo por 30 días es el balance exacto entre retener información en caliente para un campeonato y ahorrar espacio, forzando a que las estadísticas de alta frecuencia caduquen y se eliminen solas de InfluxDB.

## 2. Granularidad e Histórico (Downsampling Teórico)
Para retener información posterior a los 30 días, el equipo propuso la siguiente política teórica de *Downsampling*:
*   **Precisión original (1 seg):** Solo se usa para las métricas consultadas el día del partido.
*   **Ventanas de Agregación (1 a 5 min):** Una tarea programada debe tomar el promedio de posesión y el máximo de pases y tiros (contadores acumulados) por equipo agrupándolos en bloques de minutos, y escribirlos en una base histórica aparte (`fixture2030_historico`) sin retención. Esto achica el peso del archivo resultante en un factor de x60 a x300.

## 3. Justificación por Medida (Función de Agregación)
No todos los resúmenes funcionan igual para downsampling:
*   `usuarios_activos`: Su agregado correcto es el `MAX()` de la ventana (queremos saber el pico del minuto, no el promedio).
*   `pases_completados` / `tiros`: Son contadores, por lo que su agregado histórico final por partido es simplemente el `MAX()` global (pues nunca decrementan).
*   `posesion_pct`: Su agregado histórico debe ser `AVG()` de la ventana.

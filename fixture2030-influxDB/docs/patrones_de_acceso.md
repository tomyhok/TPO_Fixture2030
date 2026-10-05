# Patrones de Acceso Temporales (Hito 8)

El diseño del modelo multidimensional en InfluxDB parte de las preguntas que la plataforma del Fixture 2030 necesita responder de forma eficiente. No se trata simplemente de guardar un log de datos, sino de optimizar para las consultas críticas en vivo y el análisis posterior.

## 1. Evolución de Posesión y Pases
*   **Consulta:** "¿Cómo cambió la posesión y efectividad de pases de un equipo durante un partido específico?"
*   **Rango temporal:** Ventana de los últimos minutos o el transcurso del partido completo (últimas 2 horas).
*   **Filtro:** `partido_id` (para segmentar el encuentro) y `equipo_id` (para segmentar el contendiente).
*   **Medidas devueltas:** `posesion_pct`, `pases_completados`.
*   **Frecuencia esperada:** Múltiples puntos por segundo desde la telemetría del campo.

## 2. Análisis Agregado de Pico de Usuarios
*   **Consulta:** "¿Cuál fue el pico de usuarios activos (audiencia) conectados durante los momentos más importantes del torneo o de un partido?"
*   **Rango temporal:** Durante el partido, o a nivel torneo si no se filtra por partido.
*   **Filtro:** `partido_id` o ninguno (para vista global).
*   **Agregación:** `MAX(usuarios_activos)` agrupado en ventanas (ej. por cada minuto).
*   **Precisión temporal:** Segundos (para inyección) pero la consulta agrega en ventanas de 1 minuto.

## 3. Comportamiento frente a latencia (Dato Tardío)
Si un punto llega con un timestamp atrasado (ej. problema de red desde el estadio), el formato *Line Protocol* fuerza el timestamp de forma explícita. InfluxDB ordenará correctamente el punto histórico, garantizando que una consulta SQL posterior refleje la realidad secuencial en lugar del orden de llegada (ingestion time).

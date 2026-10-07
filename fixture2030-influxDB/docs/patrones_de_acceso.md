# Patrones de Acceso Temporales (Hito 8)

El diseño del modelo multidimensional en InfluxDB parte de las preguntas que la plataforma del Fixture 2030 necesita responder de forma eficiente. No se trata simplemente de guardar un log de datos, sino de optimizar para las consultas críticas en vivo y el análisis posterior.

## 1. Evolución de Posesión y Pases
*   **Consulta:** "¿Cómo cambió la posesión y efectividad de pases de un equipo durante un partido específico?"
*   **Quién genera / quién consulta:** la genera el proveedor de datos del estadio (un punto por segundo y por equipo); la consulta la pantalla de estadísticas en vivo del partido.
*   **Rango temporal:** Ventana de los últimos minutos o el transcurso del partido completo (últimas 2 horas).
*   **Filtro:** `partido_id` (para segmentar el encuentro) y `equipo_id` (para segmentar el contendiente).
*   **Medidas devueltas:** `posesion_pct`, `pases_completados`.
*   **Frecuencia esperada:** 1 punto por segundo por equipo.
*   **Precisión temporal:** segundos. Las estadísticas no cambian más rápido que eso.
*   **Implementado en:** `consultas_temporales.sh` (consultas 1 y 2).

## 2. Análisis Agregado de Pico de Usuarios
*   **Consulta:** "¿Cuál fue el pico de usuarios activos (audiencia) conectados durante los momentos más importantes del torneo o de un partido?"
*   **Quién genera / quién consulta:** lo genera la plataforma (conteo de sesiones activas, ver Hito 7); lo consulta el equipo de operación para dimensionar la infraestructura.
*   **Rango temporal:** Durante el partido, o a nivel torneo si no se filtra por partido.
*   **Filtro:** `partido_id` o ninguno (para vista global).
*   **Agregación:** `MAX(usuarios_activos)` agrupado en ventanas de 1 minuto (`date_bin`).
*   **Frecuencia esperada:** 1 punto por segundo.
*   **Precisión temporal:** Segundos (para inyección) pero la consulta agrega en ventanas de 1 minuto.
*   **Implementado en:** `agregaciones.sh` (consulta 2).

## 3. Resumen del Partido por Equipo
*   **Consulta:** "¿Cuál fue la posesión promedio, los pases y los tiros totales de cada equipo en el partido?"
*   **Quién consulta:** la ficha del partido una vez terminado, y el resumen histórico del torneo.
*   **Rango temporal:** la duración del partido.
*   **Filtro:** `partido_id`, agrupando por `equipo_id` (compara las dos dimensiones del partido).
*   **Agregación:** `AVG(posesion_pct)`, `MAX(pases_completados)`, `MAX(tiros)`, `MAX(usuarios_activos)`.
*   **Implementado en:** `agregaciones.sh` (consulta 1).

## 4. Comportamiento ante ausencia de puntos, retraso o dato tardío
*   **Ausencia de puntos:** si la fuente deja de enviar, la consulta de una ventana devuelve menos filas (o ninguna). No se inventan valores: la pantalla muestra el último dato disponible y su hora. En la agregación por minuto, un minuto sin puntos directamente no aparece.
*   **Retraso de la fuente / dato tardío:** cada punto lleva su propio timestamp en el *Line Protocol* (el momento en que ocurrió, no el de llegada). InfluxDB lo guarda en su lugar dentro de la serie, y una consulta posterior refleja el orden real de los hechos.
*   **Punto repetido:** un punto con la misma serie y el mismo timestamp reemplaza al anterior, así que reenviar un lote no duplica datos.

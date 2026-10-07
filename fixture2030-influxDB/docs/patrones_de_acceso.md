# Patrones de Acceso Temporales (Hito 8)

El modelo de InfluxDB parte de las preguntas que la plataforma del Fixture 2030 necesita responder. Cada tag, field y política temporal del [modelo](modelo_multidimensional.md) se justifica con uno o más de estos patrones.

## 1. Evolución de posesión y pases
*   **Consulta:** "¿Cómo cambiaron la posesión y los pases de un equipo durante un partido?"
*   **Quién genera / quién consulta:** la genera el proveedor de datos del estadio (un punto por segundo y por equipo); la consulta la pantalla de estadísticas en vivo del partido.
*   **Rango temporal:** los últimos minutos, o el partido completo (hasta ~2 horas).
*   **Filtro:** `partido_id` (el encuentro) y `equipo_id` (el equipo); para comparar, ambos equipos del mismo partido.
*   **Medidas devueltas:** `posesion_pct`, `pases_completados`.
*   **Frecuencia esperada:** 1 punto por segundo por equipo.
*   **Precisión temporal:** segundos. Las estadísticas no cambian más rápido que eso.
*   **Implementado en:** `consultas_temporales.sh` (consultas 1 y 2).

## 2. Pico de usuarios por minuto
*   **Consulta:** "¿Cuál fue el pico de usuarios conectados siguiendo a cada equipo, minuto a minuto?"
*   **Quién genera / quién consulta:** la genera la plataforma con el conteo de sesiones activas (Redis, Hito 7); la consulta el equipo de operación para dimensionar la infraestructura.
*   **Rango temporal:** el partido, o el torneo completo si no se filtra por partido.
*   **Filtro:** `partido_id` y `equipo_id`, o ninguno para la vista global.
*   **Agregación:** `MAX(usuarios_activos)` en ventanas de 1 minuto (`date_bin`), porque interesa el pico y no el promedio. La audiencia total del partido es la suma de los dos equipos en el mismo segundo.
*   **Frecuencia esperada:** 1 punto por segundo por equipo.
*   **Precisión temporal:** se escribe en segundos y se consulta agregado por minuto.
*   **Implementado en:** `agregaciones.sh` (consulta 2).

## 3. Resumen del partido por equipo
*   **Consulta:** "¿Cuál fue la posesión promedio y cuántos pases y tiros hizo cada equipo en el partido?"
*   **Quién genera / quién consulta:** los datos vienen de la misma fuente que el patrón 1; consultan la ficha del partido una vez terminado y el resumen histórico del torneo.
*   **Rango temporal:** la duración del partido.
*   **Filtro:** `partido_id`, agrupando por `equipo_id` (compara las dos dimensiones del partido).
*   **Agregación:** `AVG(posesion_pct)`; `MAX(pases_completados)` y `MAX(tiros)`, porque son contadores acumulados y el máximo es el total final; `MAX(usuarios_activos)` como pico.
*   **Frecuencia esperada:** se consulta una vez por partido terminado, sobre datos que llegaron a 1 punto por segundo.
*   **Precisión temporal:** alcanza con la del partido completo. Por eso este resumen sigue siendo válido después del downsampling (ver [retención](retencion_y_granularidad.md)).
*   **Implementado en:** `agregaciones.sh` (consulta 1).

## 4. Comportamiento ante ausencia de puntos, retraso o dato tardío
*   **Ausencia de puntos:** si la fuente deja de enviar, la consulta de una ventana devuelve menos filas, o ninguna. No se inventan valores: la pantalla muestra el último dato disponible y su hora. En la agregación por minuto, un minuto sin puntos directamente no aparece.
*   **Retraso de la fuente / dato tardío:** cada punto lleva su propio timestamp en el *Line Protocol* (el momento en que ocurrió, no el de llegada). InfluxDB lo guarda en su lugar dentro de la serie, y las consultas posteriores reflejan el orden real de los hechos.
*   **Punto repetido:** un punto con la misma serie y el mismo timestamp reemplaza al anterior, así que reenviar un lote no duplica datos.

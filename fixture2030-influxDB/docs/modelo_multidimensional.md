# Modelo Multidimensional (Hito 8)

El modelo en InfluxDB 3 Core se basa en la tabla `estadisticas_partido`, diseñada para soportar observaciones de alta frecuencia separando el contexto identitario (tags) de los valores medidos (fields).

## 1. Definición Estructural

| Elemento | Tipo | Descripción | Razón de la decisión |
| :--- | :--- | :--- | :--- |
| **Tabla** | Measurement | `estadisticas_partido` | Agrupa el fenómeno medido en vivo durante un encuentro de fútbol. |
| **Timestamp**| DateTime | Segundos desde Epoch | Define el instante exacto. Los scripts lo fuerzan para evitar asimetrías de red y garantizar orden. |
| **Tag** | Dimensión | `partido_id` (String) | Permite acotar las consultas al rango de un único partido, esencial para dashboards locales. |
| **Tag** | Dimensión | `equipo_id` (String) | Divide las métricas por contendiente para análisis comparativo y gráficos de torta/evolución. |
| **Field** | Medida | `posesion_pct` (Float) | Representa un porcentaje dinámico (0-100%). |
| **Field** | Medida | `pases_completados` (Integer) | Valor acumulado. Cada punto aumenta o se mantiene, ideal para consultar el máximo. |
| **Field** | Medida | `tiros` (Integer) | Contador acumulado de eventos de tiro. |
| **Field** | Medida | `usuarios_activos` (Integer)| Medida volátil (sube y baja) de la audiencia. |

## 2. Exclusiones Intencionales (Lo que NO es Tag)
**Se ha excluido intencionalmente `jugador_id` de los tags**. 
Si se agregara como tag para observar el rendimiento micro, multiplicaría la cardinalidad por la cantidad de jugadores de cada equipo (de 254 a más de 5.000 series). Ese tipo de telemetría hiper-fragmentada (heatmaps individuales, acelerómetros en botines) debería procesarse en un stream y guardarse en tablas separadas orientadas a un caso de uso distinto para no degradar el dashboard principal de partido.

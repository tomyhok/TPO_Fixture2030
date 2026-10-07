# Modelo Multidimensional (Hito 8)

El modelo en InfluxDB 3 Core se basa en una tabla, `estadisticas_partido`, que separa el contexto que identifica a la serie (tags) de los valores medidos (fields).

## 1. Fenómeno que registra

Cada fila es una foto, tomada una vez por segundo, del estado de un equipo dentro de un partido: cuánta posesión tiene, cuántos pases completó y cuántos tiros hizo hasta ese momento, y cuántos usuarios lo están siguiendo en la plataforma.

## 2. Definición estructural

| Elemento | Nombre (tipo) | Descripción | Patrón de acceso que lo usa |
| :--- | :--- | :--- | :--- |
| **Tabla** | `estadisticas_partido` | Estadísticas en vivo de un equipo durante un partido. | Todos |
| **Timestamp** | `time` (precisión: segundos) | Instante en que ocurrió la observación según la fuente del estadio, no el momento de llegada. Se declara `--precision s` en la carga. | Todos (filtro por rango y `date_bin`) |
| **Tag** | `partido_id` (string) | Partido al que pertenece la observación. | 1, 2 y 3 (filtro) |
| **Tag** | `equipo_id` (string) | Equipo dentro del partido. | 1 (filtro), 2 y 3 (agrupación y comparación) |
| **Field** | `posesion_pct` (float) | Porcentaje de posesión del equipo en ese momento (0–100). | 1 y 3 |
| **Field** | `pases_completados` (integer) | Contador acumulado de pases desde el inicio del partido; nunca baja. | 1 y 3 |
| **Field** | `tiros` (integer) | Contador acumulado de tiros desde el inicio del partido; nunca baja. | 3 |
| **Field** | `usuarios_activos` (integer) | Sesiones activas que siguen el partido con ese equipo como favorito (dato que maneja Redis en el Hito 7). Sube y baja. | 2 y 3 |

**Serie:** `estadisticas_partido` + `partido_id` + `equipo_id`. Hay dos series por partido, cada una con un punto por segundo.

## 3. Medidas: tipo, semántica y agregación correcta

| Medida | Naturaleza | Agregación correcta | Agregación incorrecta |
| :--- | :--- | :--- | :--- |
| `posesion_pct` | Muestra de un valor instantáneo (*gauge* acotado 0–100) | `AVG` en una ventana: posesión media del tramo | `SUM` no tiene sentido para un porcentaje |
| `pases_completados`, `tiros` | Contador acumulado (monótono creciente) | `MAX` = total al final de la ventana; `MAX - MIN` = cantidad ocurrida dentro de la ventana | `SUM` sumaría el mismo acumulado miles de veces |
| `usuarios_activos` | *Gauge* que sube y baja | `MAX` = pico de audiencia (dimensionar la plataforma); `AVG` = audiencia típica | `SUM` en el tiempo contaría la misma sesión una vez por segundo |

La audiencia total de un partido en un instante es la suma de `usuarios_activos` de sus dos equipos **en el mismo segundo**. Sumar valores de segundos distintos no es válido.

## 4. Exclusiones intencionales (lo que NO es tag)

*   **`jugador_id`:** si fuera tag, multiplicaría las series por la cantidad de jugadores de cada equipo (de 208 a más de 5.000) y ningún patrón de acceso lo necesita. La telemetría por jugador iría en otra tabla, pensada para otro caso de uso.
*   **Sede:** cada partido se juega en una sola sede, así que se deduce de `partido_id` consultando el fixture (Neo4j, Hito 5).
*   **Valores medidos:** son fields porque varían de forma continua. El detalle está en [`cardinalidad_y_escalabilidad.md`](cardinalidad_y_escalabilidad.md).

## 5. Diferencias entre los datos simulados y el modelo

El generador (`generacion_puntos.py`) simula cada serie por separado. Eso tiene dos consecuencias que hay que tener en cuenta al leer la evidencia:
*   En los datos reales, la posesión de los dos equipos de un partido suma 100% en cada instante. En los simulados no, porque cada equipo tiene su propio recorrido aleatorio.
*   Los identificadores de equipo son por partido (`EQ001_1`), mientras que en el torneo real `equipo_id` toma los 48 códigos de las selecciones.

Ninguna de las dos afecta la estructura del modelo, la cardinalidad (dos series por partido) ni el funcionamiento de las consultas. Solo cambian los valores que se observan.

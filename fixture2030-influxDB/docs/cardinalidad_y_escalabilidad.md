# Cardinalidad y Escalabilidad (Hito 8)

El objetivo de diseño del módulo es soportar **10M+ puntos** sin que las consultas en vivo se degraden. En InfluxDB cada combinación distinta de tags forma una serie, así que la cantidad de series (cardinalidad) depende solo de qué atributos se declaran como tags, no de cuántos puntos se cargan.

## Variación de cada dimensión

| Tag | Valores en el torneo real | Valores en el laboratorio | Por qué es tag |
| :--- | :--- | :--- | :--- |
| `partido_id` | 104 (Mundial de 48 equipos: 72 de grupos + 32 de eliminación) | 127 partidos simulados (`M001`…`M127`) | Todas las consultas filtran por partido. |
| `equipo_id` | 48 selecciones | 254 identificadores simulados, uno por equipo y partido (`EQ001_1`, `EQ001_2`, …) | Las consultas comparan o agrupan por equipo. |

En cada partido juegan solo 2 equipos, por lo que las combinaciones reales no son 104 × 48, sino 104 × 2.

## Estimación de cardinalidad

*   **Torneo real:** 104 partidos × 2 equipos = **208 series**.
*   **Laboratorio:** 127 partidos × 2 equipos = **254 series**. Lo verificó `validacion.sh` con `COUNT(DISTINCT partido_id || '/' || equipo_id)` (ver [`evidencia/06_validacion.txt`](evidencia/06_validacion.txt)).

El generador usa identificadores de equipo por partido para simplificar la simulación, por eso en el laboratorio un mismo equipo no aparece en varios partidos. La cantidad de series es igual a la del modelo real: dos por partido.

Unas pocas centenas de series es una cardinalidad baja. InfluxDB 3 guarda los datos en archivos Parquet ordenados por tags y tiempo. Con pocas series, los puntos de cada una quedan contiguos y una consulta que filtra por `partido_id` y rango de tiempo lee una porción chica de los datos. Eso explica que las consultas acotadas respondieran en menos de un segundo con 10M de puntos cargados.

## Atributos excluidos de los tags

| Atributo | Decisión | Razón |
| :--- | :--- | :--- |
| `jugador_id` | No se guarda | Multiplicaría las series por ~26 jugadores por equipo (208 → ~5.400) y ninguna consulta del módulo lo necesita. Si hiciera falta, iría en una tabla aparte. |
| Valores medidos (`posesion_pct`, `pases_completados`, `tiros`, `usuarios_activos`) | Fields | Varían de forma continua: como tags crearían una serie nueva casi en cada punto. |
| Id único de evento o de punto | No existe | El timestamp ya identifica al punto dentro de su serie; un id por punto daría una serie por punto. |
| Texto libre (comentarios, relato) | No se guarda acá | Está en el módulo de Cassandra (Hito 6). |
| Sede / estadio | No es tag | Depende del partido (cada `partido_id` se juega en una sola sede), así que se obtiene desde el fixture sin agregar series ni repetir el dato. |

## Volumen esperado y objetivo de 10M+

*   **Torneo real a 1 punto por segundo por equipo:** 104 partidos × 2 equipos × ~7.200 s (2 h, contando entretiempo y alargue) ≈ **1,5M filas** (≈ 6M valores, porque cada fila trae 4 fields).
*   **Objetivo de 10M+ filas:** es unas 7 veces el volumen real y cubre el crecimiento previsible: subir la frecuencia de captura (a 5 Hz el torneo ya da ~7,5M filas), sumar fuentes nuevas (una tabla por jugador daría ~16M filas) o conservar más de un torneo.

## Estrategia de carga

La carga está separada en tres pasos: generación (`generacion_puntos.py`), carga (`carga_lotes.sh`) y validación (`validacion.sh`).

*   **Generación de timestamps:** cada serie arranca en el inicio de su partido y avanza de a 1 segundo. La precisión es de segundos y se declara en el generador y en la carga (`--precision s`).
*   **Reparto de puntos:** el generador reparte `total / 254` puntos por serie con división entera. Por eso, al pedir 10.000.000 se generan 9.999.980 (254 × 39.370). Para superar los 10M hay que pedir 10.000.234 (254 × 39.371).
*   **Orden:** el archivo se escribe ordenado por serie y por tiempo. InfluxDB acepta igual datos desordenados o tardíos, porque cada punto trae su timestamp.
*   **Tamaño de lote:** el CLI de InfluxDB parte el archivo en lotes de 10 MiB (con ~10M de puntos fueron 139 requests de ~72.000 líneas).
*   **Concurrencia:** hasta 8 requests en paralelo (`--max-concurrent-requests 8`) y compresión `--gzip`.
*   **Errores y reintentos:** si un lote falla, el CLI corta con error y el script se detiene (`set -e`). Como un punto con la misma serie y el mismo timestamp reemplaza al anterior, se puede volver a correr la carga completa sin duplicar datos.
*   **Validación:** `validacion.sh` comprueba el total de puntos, la cantidad de partidos y de series, y que todas las series tengan la misma cantidad de puntos.

## Prueba realizada vs. objetivo

En una notebook (Apple M1 Pro, 16 GB) se cargaron **9.999.980 puntos**, 20 menos que 10M por el redondeo descrito arriba, en ~25 s de escritura (~405.000 puntos/s). El detalle está en [`evidencia/README.md`](evidencia/README.md).

Límites observados del laboratorio:
*   El archivo de ~10M de puntos ocupa 1,35 GB. Para volúmenes mucho mayores conviene generar y cargar por partes en vez de usar un único archivo.
*   En disco, los datos ocupan ~521 MB (unos 52 bytes por fila).
*   Las consultas sin rango de tiempo sobre todos los puntos tardan más de un minuto (la validación tardó 69 s), mientras que las acotadas responden en menos de un segundo.

Qué cambiaría con más carga o más fuentes:
*   Con muchas fuentes escribiendo a la vez, cada estadio enviaría sus propios lotes en paralelo en lugar de un único archivo.
*   La cardinalidad no crece con el volumen: más puntos por serie no agregan series. Solo crecería si se agregan tags (por ejemplo `jugador_id`).
*   En producción haría falta separar escritura y consulta en distintos nodos (InfluxDB 3 Enterprise) y monitorear la instancia, algo que queda fuera del alcance de este hito.

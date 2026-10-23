# Evidencia de ejecución (Hito 8)

Esta carpeta tiene dos partes:

*   **Carga de volumen (archivos `00` a `07`, 07/10/2026):** se generó con `bash tools/generar_evidencia.sh 10000000`, que corre los scripts en el orden del README y guarda la salida de cada uno.
*   **Entorno y acceso vigentes (archivos `08` y `09`, 23/10/2026):** se comprobó el servidor que usa la API del Hito 10. Ver [Verificación vigente](#verificación-vigente-23102026).

Las dos partes se hicieron en equipos distintos, así que los tiempos de la carga no se atribuyen al entorno de la verificación.

## Ambiente

| Dato | Valor |
| :--- | :--- |
| Fecha de ejecución | 2026-10-07 |
| Versión de InfluxDB | InfluxDB 3 Core 3.12.0 (imagen `influxdb:3-core`) |
| Equipo | Apple M1 Pro, 8 núcleos, 16 GB de RAM (macOS) |
| Recursos de Docker | 8 CPUs, ~8 GB de RAM |
| Punto de partida | Directorio `~/docker/data/influxdb` vacío y base recién creada |

## Resultados

| Paso | Archivo | Resultado observado |
| :--- | :--- | :--- |
| Ambiente | `00_ambiente.txt` | Versión, imagen y recursos del equipo. |
| Inicialización | `01_inicializacion.txt` | Token creado (guardado fuera del repo) y base `fixture2030` con retención de 30 días. |
| Generación | `02_generacion.txt` | 9.999.980 puntos (254 series × 39.370 puntos) en 17,3 s. Archivo de 1,35 GB. |
| Carga | `03_carga.txt` | 9.999.980 líneas en 139 requests, ~24,7 s de escritura (~405.000 puntos/s). 35,8 s en total contando el `docker cp` del archivo. |
| Consultas | `04_consultas_temporales.txt` | Ventana de 10 minutos y comparación de los dos equipos de M001: 0,57 s. |
| Agregaciones | `05_agregaciones.txt` | Resumen por equipo y agregación por minuto: 0,41 s. |
| Validación | `06_validacion.txt` | 9.999.980 puntos, 127 partidos, 254 series, 39.370 puntos en cada serie (coincide con la estrategia). Tardó 69 s. |
| Persistencia | `07_persistencia.txt` | Después de `docker restart` siguen los 9.999.980 puntos. ~521 MB en disco. |

Los tiempos son de un solo script completo (incluyen arrancar `docker exec` y el CLI), medidos con el reloj del sistema.

## Verificación vigente (23/10/2026)

Notebook con Windows 11, InfluxDB 3 Core **3.12.1** (`influxdb:3-core`; el digest figura en `08_entorno.json`). Ninguno de los dos archivos guarda el token.

| Paso | Archivo | Resultado observado |
| :--- | :--- | :--- |
| Entorno | `08_entorno.json` | Ambos Compose declaran el mismo servicio y el contenedor ejecuta esa imagen y ese comando. Registra versión, digest, montajes y hashes de los Compose. |
| Acceso | `08_entorno.json` (`acceso`) | `/health` sin token o con token inválido: 401. Con el token de `.influxdb3-token`: 200. Bases: `_internal` y `fixture2030`. |
| Datos | `08_entorno.json` (`acceso`) | `estadisticas_partido` tiene 29.000 puntos de la muestra del Hito 10: P-001 con 14.600 y P-002 con 14.400. |
| Conectividad | `09_conectividad.txt` | Diagnóstico del Hito 11 (`--modo nativo --producto influxdb`): **14 OK, 0 WARN, 0 FAIL**. Conteo acotado de 1.800 puntos, `date_bin` de 5 min, y sondas de token inválido (401), base inexistente (404) y ventana sin puntos (200 con conteo 0). |

Además, la prueba de integración `test_lectura_real[influxdb]` del Hito 10 pasó: `GET /partidos/P-001/estadisticas` devolvió 200 y `/health/dependencias` informó `influxdb=up`.

En `09_conectividad.txt` se quitó la línea de encabezado que advertía sobre la contraseña de otro motor, porque no corresponde a InfluxDB. El resto es la salida sin cambios.

**Límites de esta verificación:**

*   No se repitió la carga de 10M puntos. El servidor de esta notebook solo tiene la muestra del Hito 10, así que los scripts de consulta del Hito 8, que usan `M001`, no tienen datos para mostrar.
*   El contenedor se había creado el 15/10, con la versión anterior del Compose, y todavía publica el 8181 en todas las interfaces (`puerto_solo_localhost: false`). Se corrige recreándolo (ver Seguridad Local en el README).

## Interpretación

*   **Carga:** se pidieron 10.000.000 de puntos y se cargaron 9.999.980, porque el generador reparte `total / 254` por serie con división entera (254 × 39.370). Queda 20 puntos por debajo del objetivo de 10M+; para superarlo hay que correr `bash tools/generar_evidencia.sh 10000234` (254 × 39.371). El volumen cargado es del mismo orden que el objetivo, así que los tiempos medidos sirven para dimensionarlo. Los datos generados (1,35 GB de texto) ocupan ~521 MB en disco por la compresión de Parquet.
*   **Consultas acotadas vs. no acotadas:** las consultas que filtran por `partido_id` y rango de tiempo responden en menos de un segundo. La validación, que recorre todos los puntos sin filtro de tiempo (`COUNT DISTINCT`), tardó 69 s. Por eso todas las consultas de operación acotan tiempo y dimensiones (RNF8).
*   **Interpretación de M001:** en la ventana de 10 minutos ambos equipos tienen 599 puntos (uno por segundo, sin huecos). En esa ventana EQ001_1 completó 593 pases y EQ001_2, 558: como el contador arranca en 0 al inicio del partido, el máximo es la cantidad de pases del tramo. La agregación por minuto muestra cómo bajan los usuarios conectados siguiendo a EQ001_1 (`pico_usuarios`) y cómo los tiros acumulados solo crecen, que es lo esperado para un contador.
*   **Posesión:** los promedios de M001 (40,94% y 73,36%) suman más de 100% porque el generador simula cada equipo por separado (ver [modelo, sección 5](../modelo_multidimensional.md)). Sirven para comprobar que la consulta y la agregación funcionan, no como dato de un partido real.

## Limitaciones

*   Los datos son simulados (`generacion_puntos.py`), no vienen de un proveedor real. Cada equipo se simula por separado, así que la posesión de los dos equipos no suma 100%, y los identificadores de equipo son por partido.
*   Es una sola instancia local: no se probó escritura concurrente desde varias fuentes ni la retención en acción (los timestamps son de 2030, así que todavía no vencen). El downsampling a la base histórica está propuesto pero no implementado.
*   Con ~10M de puntos cada serie cubre ~11 horas, más que un partido real. Se eligió así para llegar al volumen objetivo con la misma cantidad de series. El torneo real a 1 punto por segundo genera ~1,5M filas (ver [cardinalidad](../cardinalidad_y_escalabilidad.md)).
*   Se usaron 127 partidos simulados en lugar de los 104 del torneo real. Eso cambia la cantidad de series (254 en vez de 208) pero no el orden de magnitud.

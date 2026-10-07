# Módulo Hito 8: Series Temporales con InfluxDB 3 Core

Este módulo resuelve el problema del Hito 8 (Estadísticas en vivo del Fixture 2030). Se utilizó **InfluxDB 3 Core** para almacenar las estadísticas de los partidos (posesión, pases, tiros, usuarios conectados) con consultas por ventana de tiempo, agregaciones y una cardinalidad controlada.

## Estructura del Módulo

*   [`docker-compose.yml`](docker-compose.yml): Servicio InfluxDB.
*   `scripts/`:
    *   `inicializacion.sh`: Crea el token de administrador (guardado fuera del repo) y la base con retención de 30 días.
    *   `generacion_puntos.py`: Genera los puntos en un archivo *Line Protocol*.
    *   `carga_lotes.sh`: Carga el archivo con el CLI de InfluxDB (lotes, GZIP y concurrencia).
    *   `consultas_temporales.sh`: Ventana temporal y comparación entre equipos.
    *   `agregaciones.sh`: Resumen por equipo y agregación por minuto.
    *   `validacion.sh`: Cuenta puntos, partidos y series, y verifica la distribución por serie.
*   `tools/generar_evidencia.sh`: Corre todo en orden y guarda la salida en `docs/evidencia/`.
*   `docs/`:
    *   [Patrones de Acceso](docs/patrones_de_acceso.md)
    *   [Modelo Multidimensional](docs/modelo_multidimensional.md)
    *   [Cardinalidad y Escalabilidad](docs/cardinalidad_y_escalabilidad.md)
    *   [Retención y Granularidad](docs/retencion_y_granularidad.md)
    *   [Evidencia](docs/evidencia/README.md)

## Problema Temporal

Durante cada partido llegan estadísticas que cambian todo el tiempo: la posesión de cada equipo, los pases completados, los tiros y la cantidad de usuarios conectados a la plataforma. La fuente envía un punto por segundo por equipo. Sumando todos los partidos del torneo y los dos equipos de cada partido, el volumen proyectado supera los 10M de puntos.

Las decisiones que se toman en tiempo real con estos datos son:
*   mostrar la evolución del partido en la pantalla de estadísticas en vivo;
*   comparar a los dos equipos en un mismo tramo del partido;
*   detectar picos de audiencia para dimensionar la plataforma.

## Ejecución del Módulo

Todos los comandos se ejecutan desde la carpeta `fixture2030-influxDB/`. Los scripts usan el contenedor `fixture2030-influxdb`, así que funcionan tanto si se levantó con este Compose como con el de la raíz del repositorio.

1. **Levantar el servicio y comprobar su estado:**
   ```bash
   mkdir -p ~/docker/data/influxdb
   docker compose up -d
   docker compose ps
   docker exec fixture2030-influxdb influxdb3 --version
   ```
2. **Inicializar (token y base de datos):**
   ```bash
   bash scripts/inicializacion.sh
   ```
3. **Generar y cargar los puntos:**
   ```bash
   python3 scripts/generacion_puntos.py 1000000 data_estadisticas.lp   # o 10000000 para 10M
   bash scripts/carga_lotes.sh
   ```
   Si no existe `data_estadisticas.lp`, `carga_lotes.sh` lo genera con 1M de puntos.
4. **Consultas, agregaciones y validación:**
   ```bash
   bash scripts/consultas_temporales.sh
   bash scripts/agregaciones.sh
   bash scripts/validacion.sh
   ```
5. **Generar la evidencia completa (opcional):**
   ```bash
   bash tools/generar_evidencia.sh 10000000
   ```
6. **Detener o reiniciar sin perder datos:**
   ```bash
   docker compose stop      # o: docker compose down
   docker compose up -d     # los datos siguen en ~/docker/data/influxdb
   ```

## Pruebas y Evidencia

Se cargaron **9.999.980 puntos** en una notebook (Apple M1 Pro, 16 GB) con InfluxDB 3 Core 3.12.0. El método, los tiempos medidos y las limitaciones están en [`docs/evidencia/README.md`](docs/evidencia/README.md), junto con la salida de cada script.

## Seguridad Local

*   El token se crea con `inicializacion.sh` y se guarda en `.influxdb3-token`, que no debe subirse al repositorio. Los scripts lo leen de ese archivo; nunca aparece escrito en el código.
*   La evidencia filtra la línea del token al guardar la salida de la inicialización.
*   El archivo generado `data_estadisticas.lp` tampoco debe subirse (pesa entre 137 MB y 1,35 GB).
*   El puerto 8181 se publica solo en `127.0.0.1` en el Compose del módulo.

## Coherencia con el TPO

*   **Partidos y equipos:** `partido_id` y `equipo_id` representan los mismos partidos y equipos que el grafo de Neo4j (Hito 5) y los comentarios de Cassandra (Hito 6). En este módulo se usan identificadores simulados (`M001`, `EQ001_1`); con datos reales se usaría el mismo identificador de partido de los otros módulos (`P-001`).
*   **Usuarios:** `usuarios_activos` es la cantidad de sesiones activas que maneja Redis (Hito 7), registrada a lo largo del tiempo.
*   **Eventos:** los goles, tarjetas y demás eventos puntuales siguen en sus módulos. Acá solo se guardan medidas numéricas que cambian en el tiempo; no se duplica la información de equipos y jugadores de MongoDB (Hito 4).

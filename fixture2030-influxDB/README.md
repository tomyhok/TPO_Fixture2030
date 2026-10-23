# Módulo Hito 8: Series Temporales con InfluxDB 3 Core

**Repositorio:** https://github.com/tomyhok/TPO_Fixture2030

Este módulo resuelve el Hito 8 (estadísticas en vivo del Fixture 2030). Usa **InfluxDB 3 Core** para guardar las estadísticas de los partidos (posesión, pases, tiros y usuarios conectados) y consultarlas por ventana de tiempo, con agregaciones y una cardinalidad controlada.

## Estructura del Módulo

*   [`docker-compose.yml`](docker-compose.yml): Servicio InfluxDB.
*   `scripts/`:
    *   `inicializacion.sh`: Crea el token de administrador (guardado fuera del repo) y la base con retención de 30 días.
    *   `generacion_puntos.py`: Genera los puntos en un archivo *Line Protocol*.
    *   `carga_lotes.sh`: Carga el archivo con el CLI de InfluxDB (lotes, GZIP y concurrencia).
    *   `consultas_temporales.sh`: Ventana temporal y comparación entre equipos.
    *   `agregaciones.sh`: Resumen por equipo y agregación por minuto.
    *   `validacion.sh`: Cuenta puntos, partidos y series, y verifica la distribución por serie.
    *   `verificar_entorno.py`: Contrasta los dos Compose con el contenedor, registra versión y digest de la imagen y prueba el token (sin guardarlo).
*   `tools/generar_evidencia.sh`: Corre todo en orden y guarda la salida en `docs/evidencia/`.
*   `docs/`:
    *   [Patrones de Acceso](docs/patrones_de_acceso.md)
    *   [Modelo Multidimensional](docs/modelo_multidimensional.md)
    *   [Cardinalidad y Escalabilidad](docs/cardinalidad_y_escalabilidad.md)
    *   [Retención y Granularidad](docs/retencion_y_granularidad.md)
    *   [Evidencia](docs/evidencia/README.md)

## Problema Temporal

Durante cada partido llegan estadísticas que cambian todo el tiempo: la posesión de cada equipo, los pases completados, los tiros y la cantidad de usuarios conectados siguiendo a cada equipo. La fuente envía un punto por segundo por equipo. Para los 127 partidos del escenario eso da unas 1,83M filas (127 × 2 equipos × ~7.200 s). El objetivo de diseño de 10M+ puntos deja margen para subir la frecuencia de captura, sumar fuentes o conservar más de un torneo (ver [cardinalidad y escalabilidad](docs/cardinalidad_y_escalabilidad.md)).

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
   Si `.influxdb3-token` ya existe, el script no crea otro: solo comprueba por HTTP que el servidor lo acepte y que exista la base. El token pertenece al directorio de datos (`~/docker/data/influxdb`) donde se creó: cada integrante tiene el suyo. Si el directorio de datos ya tiene un token de administrador y falta el archivo, el servidor no crea un segundo token. Regenerarlo con `influxdb3 create token --admin --regenerate` invalida el anterior. Lo primero es recuperar el archivo; no borrar los datos para empezar de cero.
3. **Generar y cargar los puntos:**
   ```bash
   python3 scripts/generacion_puntos.py 1000000 data_estadisticas.lp   # o 10000234 para superar los 10M
   bash scripts/carga_lotes.sh
   ```
   Si no existe `data_estadisticas.lp`, `carga_lotes.sh` lo genera con 1M de puntos. El generador reparte `total / 254` puntos por serie con división entera, así que el total cargado puede ser apenas menor al pedido (con 10.000.000 se cargan 9.999.980).
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
6. **Verificar entorno y token (no modifica datos):**
   ```bash
   python scripts/verificar_entorno.py
   ```
   Falla si los dos Compose difieren o si el contenedor no corre la imagen y el comando declarados. Sobrescribe `docs/evidencia/08_entorno.json`, así que siempre queda una sola versión vigente.
7. **Detener o reiniciar sin perder datos:**
   ```bash
   docker compose stop      # o: docker compose down
   docker compose up -d     # los datos siguen en ~/docker/data/influxdb
   ```
8. **Limpieza (opcional, borra todos los datos cargados):**
   ```bash
   docker compose down
   rm -rf ~/docker/data/influxdb/*
   rm -f .influxdb3-token data_estadisticas.lp
   ```
   Después de esto hay que volver a empezar desde el paso 1.

## Entorno

El Compose del módulo y el de la raíz declaran el mismo servicio: imagen `influxdb:3-core`, el mismo comando, el puerto 8181 publicado solo en `127.0.0.1` y los datos en `~/docker/data/influxdb`. `influxdb:3-core` identifica la familia Core y avanza con cada publicación (`pull_policy: always`). Para saber exactamente qué binario corrió, `08_entorno.json` registra la versión y el digest de la imagen.

## Pruebas y Evidencia

La evidencia está en [`docs/evidencia/`](docs/evidencia/README.md) y tiene dos partes:

*   **Carga de volumen (07/10/2026):** se cargaron **9.999.980 puntos** (se pidieron 10M; la diferencia se explica en el paso 3) en una notebook Apple M1 Pro de 16 GB con InfluxDB 3 Core 3.12.0. Para esta parte se registraron tiempos de carga, consultas, agregaciones, validación y persistencia (archivos `00` a `07`).
*   **Verificación del entorno y del acceso (23/10/2026):** se hizo en otra notebook (Windows 11) con InfluxDB 3 Core 3.12.1, contra el servidor que usa la API del Hito 10.
    *   El servidor rechaza `/health` sin token o con un token inválido (401) y acepta el token de `.influxdb3-token` (200).
    *   La base `fixture2030` existe con la tabla `estadisticas_partido`, que tiene 29.000 puntos de la muestra del Hito 10 (P-001 y P-002).
    *   El diagnóstico del Hito 11 dio 14 OK y 0 FAIL: conteo acotado por tiempo, `date_bin` de 5 minutos, base inexistente (404) y ventana sin puntos (200 con conteo 0).
    *   La API devolvió 200 en `GET /partidos/P-001/estadisticas` e informó InfluxDB `up` en `/health/dependencias`.
    *   Esta verificación no repite la carga de 10M puntos (archivos `08` y `09`).

## Seguridad Local

*   El token se crea con `inicializacion.sh` y se guarda en `.influxdb3-token`, que no debe subirse al repositorio. Los scripts lo leen de ese archivo; nunca aparece escrito en el código.
*   La evidencia filtra la línea del token al guardar la salida de la inicialización.
*   El archivo generado `data_estadisticas.lp` tampoco debe subirse (pesa entre 137 MB y 1,35 GB).
*   El puerto 8181 se publica solo en `127.0.0.1` en ambos Compose. Un contenedor creado con una versión anterior del Compose conserva su publicación anterior hasta recrearlo con `docker compose up -d --force-recreate influxdb`. Los datos y el token se conservan porque están en `~/docker/data/influxdb`. `08_entorno.json` lo indica en `puerto_solo_localhost`.

## Coherencia con el TPO

*   **Partidos y equipos:** `partido_id` y `equipo_id` representan los mismos partidos y equipos que el grafo de Neo4j (Hito 5) y los comentarios de Cassandra (Hito 6). En este módulo se usan identificadores simulados (`M001`, `EQ001_1`); con datos reales se usarían los mismos identificadores de los otros módulos (`P-001` para el partido y el código de cada selección para el equipo).
*   **Sedes:** no se guardan acá. Cada partido se juega en una sola sede, que se obtiene desde el fixture de Neo4j a partir de `partido_id`.
*   **Usuarios:** `usuarios_activos` es la cantidad de sesiones activas que maneja Redis (Hito 7) siguiendo a cada equipo, registrada a lo largo del tiempo.
*   **Eventos:** los goles, tarjetas y demás eventos puntuales siguen en sus módulos. Acá solo se guardan medidas numéricas que cambian en el tiempo; no se duplica la información de equipos y jugadores de MongoDB (Hito 4).

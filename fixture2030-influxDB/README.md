# Módulo Hito 8: Series Temporales con InfluxDB 3 Core

Este módulo resuelve el problema del Hito 8 (Estadísticas en vivo del Fixture 2030). Se utilizó **InfluxDB 3 Core** para almacenar la telemetría dinámica de los partidos (posesión, tiros, usuarios conectados) optimizando para la velocidad de inyección, consultas por ventana de tiempo, y downsampling sin estallar en cardinalidad.

## Estructura del Módulo

*   [`docker-compose.yml`](docker-compose.yml): Orquestador del servicio InfluxDB.
*   `scripts/`: Lógica de prueba reproducible.
    *   `inicializacion.sh`: Consigue credenciales seguras (Tokens) y crea la DB con retención a 30 días.
    *   `generacion_puntos.py`: Script generador masivo en Line Protocol de alta escalabilidad.
    *   `carga_lotes.sh`: Comando de ingesta usando Batching y compresión GZIP con Influx CLI.
    *   `consultas_temporales.sh` / `agregaciones.sh`: Demostración de filtros por tiempo y consultas SQL.
    *   `validacion.sh`: Cuenta el volumen de la tabla final.
*   `docs/`: Justificaciones teóricas SWEBOK obligatorias.
    *   [Patrones de Acceso](docs/patrones_de_acceso.md)
    *   [Modelo Multidimensional](docs/modelo_multidimensional.md)
    *   [Cardinalidad y Escalabilidad](docs/cardinalidad_y_escalabilidad.md)
    *   [Retención y Granularidad](docs/retencion_y_granularidad.md)

## Ejecución del Módulo (Reproducibilidad)

El entorno fue probado exitosamente en Docker. Para ejecutar la prueba de concepto:

1. **Levantar el servicio:**
   ```bash
   docker compose up -d influxdb
   ```
2. **Inicializar y obtener token:**
   ```bash
   bash scripts/inicializacion.sh
   ```
3. **Generar y Cargar (Demo Masiva):**
   *(Por defecto generará un archivo temporal de 1 Millón de puntos, tardará unos 2-3 segundos en crear el LP y otros 10 segundos en inyectar).*
   ```bash
   bash scripts/carga_lotes.sh
   ```
4. **Ejecutar Consultas y Agregaciones:**
   ```bash
   bash scripts/consultas_temporales.sh
   bash scripts/agregaciones.sh
   bash scripts/validacion.sh
   ```

## Evidencias (Limitaciones del Laboratorio Local)

Se ha proyectado la carga masiva hacia el límite sugerido (10M+). 
> **Nota para los integrantes del equipo:**
> Deben capturar la ejecución del bash completo y los logs de salida (resultados SQL de agregaciones y total de inserciones). 
> Guardar las capturas en la carpeta `docs/evidencia/`.

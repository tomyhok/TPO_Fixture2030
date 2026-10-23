# Grupo 4 — Hito 10: API REST integrada

La API integra los seis motores con **seis lecturas representativas**, una por motor.
Se priorizan contratos, validación, errores y pruebas esenciales, siguiendo la devolución docente.
Los endpoints de salud ampliados se conservan por los requisitos del Hito 11.

## Ejecutar

1. Levantar los motores desde la raíz: `docker compose up -d`.
2. En esta carpeta, crear un entorno Python 3.12 e instalar `pip install -r requirements.txt`.
3. Copiar `.env.example` a `.env` y completar las credenciales del laboratorio. No se versiona.
4. Preparar las muestras de los hitos 4–9. `bash scripts/preparar_datos.sh` reutiliza sus scripts;
   no borra datos, pero vuelve a escribir las muestras con identificadores conocidos. No ejecutar
   para conservar cambios manuales hechos sobre esos mismos identificadores.
5. Ejecutar `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Abrir `http://127.0.0.1:8000/docs`.

El token de InfluxDB no hace falta escribirlo en el `.env`. Con `INFLUX_TOKEN` vacío, la API lo lee
de `fixture2030-influxDB/.influxdb3-token`, que genera el Hito 8 y no se versiona. Si faltan los dos,
el diagnóstico informa `not_configured` y la lectura de estadísticas responde 503. En ese caso hay
que recuperar el archivo; no generar otro token ni reinicializar el almacenamiento. El 23/10/2026 se
verificó con ese archivo: `test_lectura_real[influxdb]` pasó e InfluxDB figuró `up`
([evidencia en el Hito 8](../fixture2030-influxDB/docs/evidencia/README.md#verificación-vigente-23102026)).

## Alcance actual

| Lectura | Fuente y responsabilidad |
|---|---|
| `GET /equipos/{codigo_iso}` | MongoDB: ficha de una selección |
| `GET /partidos/{codigo_partido}/eventos?limit=5` | Neo4j: eventos y protagonista, recorrido acotado |
| `GET /partidos/{codigo_partido}/comentarios?ventana=203006152015&limit=5` | Cassandra: muro de una ventana |
| `GET /sesiones/{id_sesion}` | Redis: datos públicos y TTL; sin renovación |
| `GET /partidos/{codigo_partido}/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z` | InfluxDB: agregado temporal |
| `GET /partidos-oficiales/{codigo_partido}` | IRIS: SELECT de la proyección de objetos |

La demostración del Hito 9 crea el acta `P-009`. Los demás motores usan `P-001`.
Cada ruta consulta exclusivamente su fuente. No hay caché Redis sobre Neo4j, escrituras HTTP,
coordinación de escrituras entre motores, reservas de idempotencia ni fachada ObjectScript.

Salud: `/health` verifica las seis fuentes; `/health/live` no consulta bases;
`/health/ready` permite servicio parcial; `/health/dependencias` detalla cada fuente y reutiliza
el chequeo durante un TTL configurable. Esta reutilización es del diagnóstico en memoria,
no una caché Redis de datos del negocio.

## Contratos, validación y pruebas

OpenAPI: `openapi/openapi.yaml`, regenerado con `python scripts/exportar_openapi.py`.
Entradas inválidas devuelven 400 antes de acceder a una fuente; ausencias individuales 404;
colecciones vacías 200; dependencia inaccesible 503; timeout 504. Errores internos 500 sin
credenciales, hosts ni trazas en la respuesta. `X-Request-ID` permite relacionar respuesta y log.

`python -m pytest tests/unit -q` ejecuta las pruebas esenciales y las regresiones de salud.
`python -m pytest tests/integration/test_dependencias_caidas.py -q` verifica caídas y timeouts
con clientes reales, sin detener contenedores. La integración positiva completa necesita las
seis fuentes configuradas; su salto no equivale a éxito. Postman contiene 10 solicitudes de lectura.

Evidencia vigente: [revisión de octubre](docs/evidencia/revision_2026-10-19/README.md).
Los archivos anteriores en `docs/evidencia/` describen la API ampliada previa y se conservan
como antecedentes, no como prueba de los endpoints actuales.

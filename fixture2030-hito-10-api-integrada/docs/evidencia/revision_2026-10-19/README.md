# Revisión del 19 de octubre de 2026

`http_real.json` registra **17 GET por HTTP real a Uvicorn**: nueve 200, dos 400, cuatro 404
y dos 503. Los 503 corresponden a estadísticas InfluxDB sin token. Se comprueba validación,
ausencia, listas vacías, lecturas y salud parcial. El servidor temporal se detuvo al terminar.
MongoDB, Neo4j, Cassandra e IRIS devuelven datos; Redis responde sesión no vigente correctamente.
El acta IRIS P-009 se lee por SQL/DB-API, sin fachada ni escrituras HTTP.

`lecturas_reales.json` conserva la comprobación inicial por TestClient ASGI con adaptadores reales.
No debe confundirse ese transporte con el de la captura HTTP posterior.

`pruebas.txt`: **61 aprobadas, 1 omitida** (46 unitarias, 10 de fallas de conexión/timeout,
5 lecturas reales; falta la sexta, InfluxDB). `pruebas_h11.txt`: 42 aprobadas del diagnóstico.
La omisión y los 503 no se presentan como integración positiva de InfluxDB. Falta recuperar su token
para repetir consultas del Hito 8 y completar su lectura vía API.

Las marcas están en UTC; la ejecución fue durante el 19 de octubre en Argentina. No se
usan estos tiempos puntuales para garantizar los objetivos de rendimiento del escenario.

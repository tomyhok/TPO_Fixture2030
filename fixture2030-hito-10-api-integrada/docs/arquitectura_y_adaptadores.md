# Arquitectura y adaptadores

El recorrido de una solicitud es ruta FastAPI → servicio → adaptador → motor.
Las rutas validan formato y límites; los servicios validan intervalos y distinguen ausencia;
los adaptadores parametrizan las consultas y traducen errores del cliente de cada motor.
`app/dependencias.py` compone las seis dependencias e intercambia adaptadores por dobles en pruebas.

MongoDB usa una proyección documental; Neo4j un recorrido Cypher limitado; Cassandra lee
las particiones completas del muro, sin escrituras ni filtros libres; Redis lee hash y TTL;
InfluxDB recibe SQL con parámetros y una resolución elegida de una lista cerrada; IRIS usa
DB-API con SELECT parametrizados sobre las clases del Hito 9. IRIS serializa el acceso a su
conexión y limita externamente la espera; los demás clientes tienen límites de conexión y operación.
No se reintentan operaciones de negocio automáticamente.

No hay dependencias cruzadas entre casos. Si MongoDB falla, los eventos de Neo4j siguen disponibles.
El consumidor recibe 503/504 identificando la fuente; el detalle del driver queda en el log.
El cierre de la aplicación libera los clientes. La evaluación distribuida de CAP es conceptual
del Hito 3; estos contenedores locales no demuestran disponibilidad geográfica ni latencia de producción.

# Conectividad y configuración

Copiar `.env.example` a `.env` y completar las credenciales existentes. El archivo está ignorado.
Las rutas y puertos del ejemplo corresponden al Compose raíz, con la API ejecutada en la notebook.
Para ejecutar dentro de Docker deben usarse nombres de servicio, no `127.0.0.1` de otro contenedor.

MongoDB requiere su usuario, contraseña y base de autenticación; Neo4j su usuario, contraseña
y database. Cassandra y Redis no tienen autenticación en este laboratorio. InfluxDB necesita
el token del servidor existente: se toma de `INFLUX_TOKEN` o del archivo `.influxdb3-token` del
Hito 8. No confundir respuesta HTTP del puerto con autorización para leer datos.

IRIS requiere usuario y contraseña en namespace USER, acceso de lectura a la base y SELECT sobre
el esquema Fixture. `scripts/preparar_datos.sh` crea una identidad dedicada si no existe; no cambia
la contraseña de una cuenta existente. La API lee por DB-API en el Superserver 1972, no por el
Management Portal 52773. No requiere cargar Fixture.API ni conceder escrituras a la identidad HTTP.

En esta revisión se creó una identidad local de lectura y un `.env` local. No se publica su contraseña.
El token de InfluxDB sigue faltando. El diagnóstico lo informa como `not_configured` sin imprimir secretos.

Los límites `TIMEOUT_CONEXION_S` y `TIMEOUT_OPERACION_S` acotan esperas.
`HEALTH_CACHE_TTL_S` y `HEALTH_UMBRAL_LENTO_MS` controlan el diagnóstico del Hito 11.

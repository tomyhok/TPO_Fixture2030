# Casos de uso — alcance corregido del Hito 10

Seis casos de negocio, uno por modelo. [Rutas y ejemplos](../README.md#alcance-actual).

Los consumen las pantallas de selección, cronología, muro de hinchas, acceso del usuario,
estadísticas y acta oficial, respectivamente. La entrada y salida de cada ruta está tipada en
OpenAPI. Todas son GET sin cambios de dominio: repetirlas es seguro e idempotente en ese
sentido, aunque el contenido pueda variar por nuevos datos o por vencimiento de una sesión.
No hay escrituras HTTP a las que aplicar prevención de duplicados o conflictos de transición.

1. **Selección**: recibir un código ISO de tres letras mayúsculas; devolver la ficha documental
   de MongoDB. Si no existe, 404. No se consulta ni lista el plantel.
2. **Eventos**: recibir un código de partido y un límite de 1–200; recorrer en Neo4j los eventos
   asociados y sus protagonistas. Partido sin eventos devuelve una lista vacía; partido inexistente, 404.
3. **Comentarios**: recibir partido, minuto UTC y límite de 1–100; consultar las cuatro particiones
   del modelo del Hito 6 y ordenar por timeuuid. El cursor continúa la lectura. Una ventana vacía es 200.
4. **Sesión**: recibir identificador; leer el hash y TTL de Redis, sin renovarlo ni invalidarlo.
   Una clave inexistente o vencida devuelve 404 `SESION_NO_VIGENTE`.
5. **Estadísticas**: recibir intervalo con zona horaria, de hasta tres horas, resolución 10s/1m/5m
   y equipo opcional; devolver agregaciones de InfluxDB. Intervalo sin puntos es 200 con series vacías.
6. **Acta oficial**: recibir código; consultar mediante DB-API y SQL parametrizado la proyección
   persistente de IRIS, incluido árbitro y eventos. Ausencia devuelve 404.

Cada caso tiene una sola dependencia. La lectura del acta no ejecuta reglas de escritura: la regla
del Hito 9 se demuestra allí mediante objetos. El diagnóstico de salud se documenta separadamente
en el Hito 11. No se amplía la funcionalidad del torneo para demostrar la integración.

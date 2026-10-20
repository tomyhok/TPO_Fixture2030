# Revisión vigente tras las correcciones docentes

La corrida `feedback_completo` incluye los seis motores y la API por **HTTP real** a un Uvicorn
temporal local, que se apagó al terminar. Se usan los clientes oficiales, el modelo IRIS simplificado
y las seis lecturas de negocio de la API reducida. No se provocan cambios en datos de dominio.

- [Matriz y detalle](feedback_completo.md).
- [JSON](feedback_completo.json) y [salida completa](feedback_completo.txt).

Resultado: **76 OK, 4 WARN, 2 FAIL, 9 SKIP**, salida estricta **1**. MongoDB, Neo4j, Cassandra,
Redis e IRIS disponibles; InfluxDB **no configurado** por falta de token. Los dos FAIL son las
lecturas HTTP de estadísticas; las capas nativas de InfluxDB no se ejecutan sin configuración.
Los WARN incluyen el diagnóstico de disponibilidad parcial y la sesión Redis ausente/vencida.
Las sondas de los cinco motores configurados terminaron correctamente.

Pruebas: 61 aprobadas y una omitida en API; 42 aprobadas en Hito 11. La prueba omitida es
la lectura real de InfluxDB; no se cuenta como éxito. El uso de localhost es el de la notebook.
El puerto HTTP temporal registrado en los archivos solo corresponde a esta corrida.

---

## Primera revisión, anterior a estas correcciones

# Verificación posterior a las correcciones

Corrida del 19/10/2026, desde la notebook y contra los puertos publicados de Docker.
Código base `c55b302`, con correcciones locales sin commit. El JSON contiene la
marca de tiempo, versiones de drivers y estado del árbol de trabajo.

Se evaluaron **MongoDB, Neo4j, Cassandra y Redis**, en modo nativo y estricto,
con las credenciales locales del `.env` raíz. InfluxDB e IRIS no forman parte de
esta corrida posterior a las correcciones: falta el token del primero y el modelo
instalado del segundo es incompatible con la fachada de la API.

- [Salida completa](nativo_corregido.txt).
- [Resultados estructurados y matriz](nativo_corregido.json).

Resultado: **43 OK, 1 WARN, 1 FAIL, 2 SKIP**. Código de salida: **1**.

MongoDB, Neo4j y Redis respondieron a sus drivers oficiales. Redis informó la
sesión de muestra ausente o vencida, sin confundirla con una caída. Cassandra
aceptó CQL, pero no tiene el keyspace `fixture2030`: falló el contexto y no se
presentaron errores de keyspace como éxitos de las sondas de partición.

Además se ejecutaron 42 pruebas del diagnóstico y 136 pruebas unitarias de la API,
todas aprobadas. Las sondas negativas de InfluxDB se verificaron con respuestas
simuladas correctas e incorrectas; no se las presenta como una medición contra el
servidor real sin su token.

Esta evidencia no reemplaza ni confirma los resultados históricos del 17/10.
Una vez preparado el entorno, debe repetirse el modo completo con la API iniciada.

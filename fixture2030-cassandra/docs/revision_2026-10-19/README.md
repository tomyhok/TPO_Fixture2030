# Corrección de persistencia — RNF2

Compose raíz y Compose del módulo montan el mismo volumen nombrado Docker:
`fixture2030_cassandra_data:/var/lib/cassandra`. No es un bind mount del directorio del host.

Para un laboratorio que todavía usa el montaje anterior, ejecutar desde la raíz:
`python fixture2030-cassandra/tools/migrar_volumen.py`. El script detiene únicamente Cassandra,
copia al volumen si está vacío, compara SHA-256 de cada archivo y recrea solo ese servicio.
Conserva la imagen instalada y el origen; si el servicio no vuelve saludable intenta restaurar
el montaje anterior. Requiere Docker disponible. No ejecutar sobre un volumen destino con datos.

En esta máquina se verificaron **147 archivos**, idénticos antes y después de la copia,
y el contenedor volvió saludable. [Manifiesto](migracion_volumen.json).
El directorio original quedó intacto como respaldo. El laboratorio no tenía el keyspace
`fixture2030`; luego se ejecutaron los scripts idempotentes de esquema y muestra (35 comentarios).
Esta muestra no reemplaza ni pretende repetir la evidencia histórica de carga superior a un millón.

Los resultados de rendimiento previos corresponden al bind mount original. Cambiar el tipo de
persistencia no permite atribuirle aquellos tiempos al volumen nombrado sin repetir las mediciones.

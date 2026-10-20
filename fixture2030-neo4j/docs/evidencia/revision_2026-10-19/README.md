# Evidencia real — Hito 5

`ejecucion.json` contiene versión, sentencias ejecutadas, filas devueltas, contadores y hashes
de los scripts. La segunda carga mantiene exactamente los mismos conteos de nodos y relaciones
y no crea duplicados. Se cargan los JSON versionados de equipos y jugadores del Hito 4.

El CRUD usa el identificador reservado `EV-H5-DEMO`, comprueba que no exista antes de empezar,
lo crea, lo consulta, cambia su minuto de 45 a 47 y elimina ese mismo evento de demostración.
La verificación final encuentra cero nodos con ese identificador. No se elimina el evento EV-002
que pudiera haber creado otra persona. Los tres recorridos del script están registrados con sus filas.

La captura siguiente se obtuvo ejecutando la consulta en **Neo4j Browser conectado al servidor
local**. Es una visualización auténtica, no un diagrama dibujado a partir del modelo:

![Recorrido de jugadores, equipo, partido y sede en Neo4j Browser](browser_grafo.png)

La consulta devuelve ocho caminos de tres saltos; el Browser informó 11 nodos y 10 relaciones.
La captura acredita visualización, no rendimiento de producción. Los tiempos corresponden solo
a esta consulta y máquina. Para repetir los resultados de scripts, ejecutar
`python fixture2030-neo4j/tools/generar_evidencia.py` desde la raíz con las dependencias de la API.
La captura debe repetirse en el Browser: el generador no fabrica imágenes de interfaz.

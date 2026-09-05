// queries/carga.cypher - Carga masiva e idempotente (RF5, RF6, RNF4)

// 1. Cargar 64 Equipos desde el JSON de MongoDB
CALL apoc.load.json("file:///equipos.json") YIELD value
MERGE (e:Equipo {codigo_iso: value._id})
SET e.nombre = value.nombre,
    e.confederacion = value.confederacion;

// 2. Cargar 1472 Jugadores desde el JSON de MongoDB y vincularlos a su Selección
CALL apoc.load.json("file:///jugadores.json") YIELD value
MERGE (j:Jugador {id_jugador: value._id})
SET j.nombre = value.nombre,
    j.posicion = value.posicion
WITH j, value
MATCH (e:Equipo {codigo_iso: value.codigo_equipo})
MERGE (j)-[:PERTENECE_A]->(e);

// 3. Crear Sedes de muestra para la programación
MERGE (s1:Sede {codigo_sede: 'MON'}) SET s1.nombre = 'Estadio Monumental', s1.ciudad = 'Buenos Aires'
MERGE (s2:Sede {codigo_sede: 'CEN'}) SET s2.nombre = 'Estadio Centenario', s2.ciudad = 'Montevideo'
MERGE (s3:Sede {codigo_sede: 'BER'}) SET s3.nombre = 'Estadio Santiago Bernabéu', s3.ciudad = 'Madrid';

// 4. Crear Partidos de muestra y conectarlos (Equipos y Sedes)
MERGE (p1:Partido {codigo_partido: 'P-001'}) SET p1.fecha = date('2030-06-10'), p1.fase = 'Grupos'
MERGE (p2:Partido {codigo_partido: 'P-002'}) SET p2.fecha = date('2030-06-12'), p2.fase = 'Grupos'

WITH p1, p2
MATCH (arg:Equipo {codigo_iso: 'ARG'}), (esp:Equipo {codigo_iso: 'ESP'}), (uru:Equipo {codigo_iso: 'URU'})
MATCH (mon:Sede {codigo_sede: 'MON'}), (cen:Sede {codigo_sede: 'CEN'})
MERGE (arg)-[:DISPUTA {condicion: 'local'}]->(p1)
MERGE (esp)-[:DISPUTA {condicion: 'visitante'}]->(p1)
MERGE (p1)-[:SE_JUEGA_EN]->(mon)

MERGE (uru)-[:DISPUTA {condicion: 'local'}]->(p2)
MERGE (arg)-[:DISPUTA {condicion: 'visitante'}]->(p2)
MERGE (p2)-[:SE_JUEGA_EN]->(cen);

// 5. Crear Eventos deportivos de muestra y conectarlos (Partidos y Jugadores)
MATCH (p1:Partido {codigo_partido: 'P-001'}), (messi:Jugador {id_jugador: 'ARG-10'})
MERGE (ev1:Evento {id_evento: 'EV-001'}) 
SET ev1.minuto = 23, ev1.tipo = 'Gol'
MERGE (ev1)-[:CORRESPONDE_A]->(p1)
MERGE (messi)-[:PROTAGONIZA]->(ev1);
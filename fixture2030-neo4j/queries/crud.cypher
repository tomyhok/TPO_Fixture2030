// queries/crud.cypher - Operaciones básicas (RF7)

// 1. CREATE: Agregar una Tarjeta Amarilla al partido P-001
MATCH (p:Partido {codigo_partido: 'P-001'})
MATCH (j:Jugador {id_jugador: 'ESP-5'}) // Suponiendo que existe un jugador de España con este ID
MERGE (ev2:Evento {id_evento: 'EV-002'})
SET ev2.tipo = 'Tarjeta Amarilla', ev2.minuto = 45
MERGE (j)-[:PROTAGONIZA]->(ev2)
MERGE (ev2)-[:CORRESPONDE_A]->(p);

// 2. READ: Leer el evento recién creado con su jugador y partido
MATCH (j:Jugador)-[:PROTAGONIZA]->(ev:Evento {id_evento: 'EV-002'})-[:CORRESPONDE_A]->(p:Partido)
RETURN j.nombre AS Infractor, ev.tipo AS Sancion, ev.minuto AS Minuto, p.codigo_partido AS Partido;

// 3. UPDATE: Cambiar el minuto de la tarjeta (de 45 a 47 por tiempo adicionado)
MATCH (ev:Evento {id_evento: 'EV-002'})
SET ev.minuto = 47
RETURN ev;

// 4. DELETE: Anular la tarjeta (Borrar el nodo y sus relaciones de forma segura)
MATCH (ev:Evento {id_evento: 'EV-002'})
DETACH DELETE ev;
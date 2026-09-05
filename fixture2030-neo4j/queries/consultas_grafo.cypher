// queries/consultas_grafo.cypher - RF8

// 1. Conocer los rivales de un equipo específico a través de los partidos compartidos
MATCH (equipo:Equipo {codigo_iso: 'ARG'})-[r1:DISPUTA]->(p:Partido)<-[r2:DISPUTA]-(rival:Equipo)
RETURN p.fecha AS Fecha, 
       p.fase AS Fase, 
       rival.nombre AS Rival, 
       r2.condicion AS Condicion_Rival
ORDER BY p.fecha;

// 2. Listar jugadores que jugarán en una sede específica (3 saltos)
MATCH (j:Jugador)-[:PERTENECE_A]->(e:Equipo)-[:DISPUTA]->(p:Partido)-[:SE_JUEGA_EN]->(sede:Sede {codigo_sede: 'MON'})
RETURN j.nombre AS Jugador, 
       j.posicion AS Posicion, 
       e.nombre AS Seleccion, 
       p.fecha AS Fecha_Partido
ORDER BY p.fecha, e.nombre, j.nombre
LIMIT 15;


// queries/consultas_grafo.cypher - RF9 (Análisis Relacional de Centralidad)

// Descubrir las sedes más centrales del torneo (Hubs logísticos)
MATCH (e:Equipo)-[:DISPUTA]->(p:Partido)-[:SE_JUEGA_EN]->(s:Sede)
RETURN s.nombre AS Estadio, 
       s.ciudad AS Ciudad, 
       count(DISTINCT e) AS Selecciones_Distintas, 
       count(DISTINCT p) AS Cantidad_Partidos
ORDER BY Selecciones_Distintas DESC, Cantidad_Partidos DESC;
// Versión final sin IRIS: el estado del partido y el árbitro pasan al grafo del Hito 5.
// Idempotente. Vuelve todos los partidos a su estado inicial (P-001 en juego, el resto
// programado: P-002 y la fase de grupos de cargar_fase_grupos.py) y borra lo que agregó la
// simulación del portal (eventos con `simulado` y la hora de inicio).
// Lo ejecuta scripts/reiniciar_demo.py (también desde preparar_datos.sh y reiniciar_muestra.ps1).

CREATE CONSTRAINT arbitro_dni IF NOT EXISTS FOR (a:Arbitro) REQUIRE a.dni IS UNIQUE;

MERGE (a:Arbitro {dni: '30111222'})
SET a.nombre = 'Facundo', a.apellido = 'Tello', a.rango = 'FIFA';

MATCH (ev:Evento {simulado: true}) DETACH DELETE ev;

// Estados válidos: Programado -> En Juego -> Finalizado (la API valida las transiciones).
MATCH (p:Partido)
SET p.estado = CASE p.codigo_partido WHEN 'P-001' THEN 'En Juego' ELSE 'Programado' END
REMOVE p.inicio;

MATCH (a:Arbitro {dni: '30111222'}), (p:Partido)
WHERE p.codigo_partido IN ['P-001', 'P-002']
MERGE (a)-[:DIRIGE]->(p);

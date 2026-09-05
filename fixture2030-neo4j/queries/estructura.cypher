// queries/estructura.cypher - Restricciones de unicidad (RF10)

CREATE CONSTRAINT equipo_codigo_iso IF NOT EXISTS
FOR (e:Equipo)
REQUIRE e.codigo_iso IS UNIQUE;

CREATE CONSTRAINT jugador_id IF NOT EXISTS
FOR (j:Jugador)
REQUIRE j.id_jugador IS UNIQUE;

CREATE CONSTRAINT sede_codigo IF NOT EXISTS
FOR (s:Sede)
REQUIRE s.codigo_sede IS UNIQUE;

CREATE CONSTRAINT partido_codigo IF NOT EXISTS
FOR (p:Partido)
REQUIRE p.codigo_partido IS UNIQUE;

CREATE CONSTRAINT evento_id IF NOT EXISTS
FOR (ev:Evento)
REQUIRE ev.id_evento IS UNIQUE;// queries/estructura.cypher - Restricciones de unicidad (RF10)

CREATE CONSTRAINT equipo_codigo_iso IF NOT EXISTS
FOR (e:Equipo)
REQUIRE e.codigo_iso IS UNIQUE;

CREATE CONSTRAINT jugador_id IF NOT EXISTS
FOR (j:Jugador)
REQUIRE j.id_jugador IS UNIQUE;

CREATE CONSTRAINT sede_codigo IF NOT EXISTS
FOR (s:Sede)
REQUIRE s.codigo_sede IS UNIQUE;

CREATE CONSTRAINT partido_codigo IF NOT EXISTS
FOR (p:Partido)
REQUIRE p.codigo_partido IS UNIQUE;

CREATE CONSTRAINT evento_id IF NOT EXISTS
FOR (ev:Evento)
REQUIRE ev.id_evento IS UNIQUE;
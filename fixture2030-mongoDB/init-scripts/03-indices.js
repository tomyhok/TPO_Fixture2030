// 03-indices.js — índices que optimizan las consultas del módulo (RF12, RNF4)
// Se ejecuta automáticamente al inicializar el contenedor o manualmente:
//   mongosh ... --file /docker-entrypoint-initdb.d/03-indices.js

print("=== Creando índices para 'equipos' ===");

// 1. Índice único sobre codigo_iso (exigido por RF12 / integridad referencial de equipos)
db.equipos.createIndex({ codigo_iso: 1 }, { name: "idx_codigo_iso_unico", unique: true });

// 2. Equipos de un grupo (consulta 2 de queries/02-consultas.js)
db.equipos.createIndex({ grupo: 1 }, { name: "idx_grupo" });

// 3. Tabla de equipos ordenada por ranking FIFA, con paginación (consulta 5)
db.equipos.createIndex({ ranking_fifa: 1 }, { name: "idx_ranking" });


print("=== Creando índices para 'jugadores' ===");

// 4. Índice normal sobre codigo_equipo (exigido por RF12 / clave foránea hacia equipos)
db.jugadores.createIndex({ codigo_equipo: 1 }, { name: "idx_codigo_equipo" });

// 5. Índices compuestos para jugadores de un equipo filtrados por posición (consulta 3)
db.jugadores.createIndex({ codigo_equipo: 1, posicion: 1 }, { name: "idx_equipo_posicion" });
db.jugadores.createIndex({ equipo_id: 1, posicion: 1 }, { name: "idx_equipo_id_posicion" });

// 6. Ranking de goleadores del torneo (consulta 4)
db.jugadores.createIndex({ "estadisticas.goles": -1 }, { name: "idx_goles" });

// 7. Integridad de negocio: un dorsal no se repite dentro del mismo equipo
db.jugadores.createIndex({ codigo_equipo: 1, dorsal: 1 }, { name: "idx_dorsal_unico", unique: true });

print("");
print("Índices creados en 'equipos':");
db.equipos.getIndexes().forEach(function (i) { print("  " + i.name + " -> " + JSON.stringify(i.key)); });

print("Índices creados en 'jugadores':");
db.jugadores.getIndexes().forEach(function (i) { print("  " + i.name + " -> " + JSON.stringify(i.key)); });


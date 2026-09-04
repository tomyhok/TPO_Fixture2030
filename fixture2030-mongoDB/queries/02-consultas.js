// 02-consultas.js — consultas sobre equipos y jugadores (RF10)
// Uso: mongosh fixture2030 --file /queries/02-consultas.js

print("==================================================");
print(" 1. IDENTIFICACIÓN DIRECTA (Por Clave)");
print("==================================================");
print("a) Equipo con codigo_iso 'ARG':");
printjson(db.equipos.findOne({ codigo_iso: "ARG" }));

print("\nb) Jugador con _id 'ARG-10':");
printjson(db.jugadores.findOne({ _id: "ARG-10" }));

print("\n==================================================");
print(" 2. FILTRADO (Por condición de negocio)");
print("==================================================");
print("Equipos clasificados en el Grupo A:");
db.equipos.find({ grupo: "A" }).forEach(function (e) {
  print("  [" + e.codigo_iso + "] " + e.nombre + " (" + e.confederacion + ") - Ranking FIFA: #" + e.ranking_fifa);
});

print("\n==================================================");
print(" 3. FILTRADO + PROYECCIÓN");
print("==================================================");
print("Defensores de Brasil (BRA), proyectando solo nombre, dorsal, posición y altura:");
db.jugadores
  .find(
    { codigo_equipo: "BRA", posicion: { $in: ["DEF", "Defensor"] } },
    { _id: 0, nombre: 1, dorsal: 1, posicion: 1, altura_cm: 1 }
  )
  .forEach(function (j) {
    print("  #" + j.dorsal + " " + j.nombre + " (" + j.posicion + ") - " + j.altura_cm + " cm");
  });

print("\n==================================================");
print(" 4. ORDENAMIENTO (Top 10 Goleadores del Torneo)");
print("==================================================");
print("Top 10 jugadores ordenados descendentemente por cantidad de goles:");
db.jugadores
  .find({}, { _id: 0, nombre: 1, codigo_equipo: 1, "estadisticas.goles": 1 })
  .sort({ "estadisticas.goles": -1 })
  .limit(10)
  .forEach(function (j, idx) {
    print("  " + (idx + 1) + ". " + j.nombre + " (" + j.codigo_equipo + ") - " + j.estadisticas.goles + " goles");
  });

print("\n==================================================");
print(" 5. PAGINACIÓN (Equipos por Ranking FIFA)");
print("==================================================");
print("Equipos ordenados por ranking - Página 2 (10 por página, skip 10):");
const limitePorPagina = 10;
const pagina = 2;
db.equipos
  .find({}, { _id: 0, codigo_iso: 1, nombre: 1, confederacion: 1, ranking_fifa: 1 })
  .sort({ ranking_fifa: 1 })
  .skip((pagina - 1) * limitePorPagina)
  .limit(limitePorPagina)
  .forEach(function (e) {
    print("  #" + e.ranking_fifa + ". " + e.nombre + " (" + e.codigo_iso + ") - " + e.confederacion);
  });


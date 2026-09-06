// 02-consultas.js — consultas sobre equipos y jugadores (RF10)
// Uso: mongosh fixture2030 --file /queries/02-consultas.js

print("==================================================");
print(" 1. IDENTIFICACIÓN DIRECTA (Por Clave)");
print("==================================================");
print("a) Equipo con _id 'ARG':");
printjson(db.equipos.findOne({ _id: "ARG" }));

print("\nb) Jugador con _id 'ARG-10':");
printjson(db.jugadores.findOne({ _id: "ARG-10" }));

print("\n==================================================");
print(" 2. FILTRADO POR CONFEDERACIÓN");
print("==================================================");
print("Equipos pertenecientes a CONMEBOL:");
db.equipos.find({ confederacion: "CONMEBOL" }).forEach(function (e) {
  print("  [" + e.codigo_iso + "] " + e.nombre + " - Grupo " + e.grupo);
});

print("\n==================================================");
print(" 3. FILTRADO + PROYECCIÓN");
print("==================================================");
print("Defensores de Argentina (ARG), proyectando nombre, dorsal y club:");
db.jugadores
  .find(
    { codigo_equipo: "ARG", posicion: "DEF" },
    { _id: 0, nombre: 1, dorsal: 1, club_actual: 1 }
  )
  .forEach(function (j) {
    print("  #" + j.dorsal + " " + j.nombre + " - " + j.club_actual);
  });

print("\n==================================================");
print(" 4. ORDENAMIENTO Y PAGINACIÓN");
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


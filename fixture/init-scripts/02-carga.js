// 02-carga.js — carga los 64 equipos y los 1472 jugadores (RF4, RF5, RF8, RNF2, RNF3)
// Se ejecuta solo al levantar el contenedor por primera vez, y tambien a mano:
//   mongosh ... --file /docker-entrypoint-initdb.d/02-carga.js

const fs = require("fs");
const DATOS = "/docker-entrypoint-initdb.d/data";

// Cada documento trae su propio _id y codigo_iso/codigo_equipo.
// El upsert reemplaza el documento existente en lugar de insertar uno nuevo:
// La carga es 100% idempotente (se puede repetir sin duplicar datos).
function cargar(coleccion, archivo) {
  const ruta = DATOS + "/" + archivo;
  const documentos = JSON.parse(fs.readFileSync(ruta, "utf8"));

  const operaciones = documentos.map(function (doc) {
    // Normalización de compatibilidad para asegurar cumplimiento del esquema
    if (!doc.codigo_iso && doc._id) doc.codigo_iso = doc._id;
    if (!doc.codigo_equipo && doc.equipo_id) doc.codigo_equipo = doc.equipo_id;
    if (!doc.equipo_id && doc.codigo_equipo) doc.equipo_id = doc.codigo_equipo;

    return {
      replaceOne: {
        filter: { _id: doc._id },
        replacement: doc,
        upsert: true
      }
    };
  });

  const r = db.getCollection(coleccion).bulkWrite(operaciones);
  print(coleccion + ": " + r.upsertedCount + " insertados, " + r.modifiedCount + " actualizados.");
}

print("=== Iniciando carga reproducible de datos ===");
cargar("equipos", "equipos.json");
cargar("jugadores", "jugadores.json");

// Verificación de la carga y de la integridad de las referencias (RNF2, RNF3)
print("");
const totalEquipos = db.equipos.countDocuments();
const totalJugadores = db.jugadores.countDocuments();
print("Equipos cargados:   " + totalEquipos + " (Objetivo RF4: 64)");
print("Jugadores cargados: " + totalJugadores + " (Objetivo RF5: >= 1000)");

const codigosIsoValidos = db.equipos.distinct("codigo_iso");
const huerfanos = db.jugadores.countDocuments({
  $and: [
    { codigo_equipo: { $nin: codigosIsoValidos } },
    { equipo_id: { $nin: codigosIsoValidos } }
  ]
});
print("Jugadores sin equipo valido (huerfanos): " + huerfanos);


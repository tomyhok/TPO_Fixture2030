// 03-agregacion.js — Pipeline de agregación de jugadores por equipo (RF11)
// Uso: mongosh fixture2030 --file /queries/03-agregacion.js

print("================================================================================");
print(" REPORTE DE JUGADORES CARGADOS POR EQUIPO (RF11)");
print("================================================================================");

const pipeline = [
  {
    $group: {
      _id: "$codigo_equipo",
      totalJugadores: { $sum: 1 }
    }
  },
  {
    $sort: { totalJugadores: -1 }
  }
];

const resultados = db.jugadores.aggregate(pipeline).toArray();

resultados.forEach(function (r) {
  print("Equipo: " + r._id + " | Total de jugadores: " + r.totalJugadores);
});


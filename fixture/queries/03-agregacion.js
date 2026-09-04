// 03-agregacion.js — Pipeline de Agregación para Inteligencia de Negocio (RF11)
// Uso: mongosh fixture2030 --file /queries/03-agregacion.js

print("================================================================================");
print(" REPORTE CONSOLIDADO: RENDIMIENTO GOLEADOR Y PLANTELES POR CONFEDERACIÓN (RF11)");
print("================================================================================");

// Pipeline analítico:
// 1. $lookup: vincula 'jugadores' con 'equipos' mediante codigo_equipo <-> codigo_iso.
// 2. $unwind: aplana el subdocumento del equipo referenciado.
// 3. $group: agrupa por confederación calculando total de jugadores, goles, promedio y récord individual.
// 4. $project: formatea métricas y redondea cálculos.
// 5. $sort: ordena las confederaciones de mayor a menor efectividad goleadora.

const pipeline = [
  {
    $lookup: {
      from: "equipos",
      localField: "codigo_equipo",
      foreignField: "codigo_iso",
      as: "datos_equipo"
    }
  },
  {
    $unwind: "$datos_equipo"
  },
  {
    $group: {
      _id: "$datos_equipo.confederacion",
      total_jugadores: { $sum: 1 },
      total_goles: { $sum: "$estadisticas.goles" },
      promedio_goles_jugador: { $avg: "$estadisticas.goles" },
      max_goles_individual: { $max: "$estadisticas.goles" }
    }
  },
  {
    $project: {
      confederacion: "$_id",
      total_jugadores: 1,
      total_goles: 1,
      promedio_goles: { $round: ["$promedio_goles_jugador", 2] },
      max_goles_individual: 1,
      _id: 0
    }
  },
  {
    $sort: { total_goles: -1 }
  }
];

const resultados = db.jugadores.aggregate(pipeline).toArray();

resultados.forEach(function (r) {
  print("Confederación: " + r.confederacion);
  print("  • Plantel consolidado:  " + r.total_jugadores + " jugadores");
  print("  • Goles totales:        " + r.total_goles);
  print("  • Promedio por jugador: " + r.promedio_goles + " goles/jugador");
  print("  • Récord individual:    " + r.max_goles_individual + " goles");
  print("------------------------------------------------------------------");
});


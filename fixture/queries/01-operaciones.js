// 01-operaciones.js — Inserciones y Actualizaciones controladas (RF9, RNF3)
// Uso: mongosh fixture2030 --file /queries/01-operaciones.js

print("==================================================");
print(" 1. INSERCIÓN DE NUEVO EQUIPO (VALIDADA)");
print("==================================================");
try {
  db.equipos.insertOne({
    _id: "ITA",
    codigo_iso: "ITA",
    nombre: "Italia",
    confederacion: "UEFA",
    grupo: "P",
    director_tecnico: "Luciano Spalletti",
    ranking_fifa: 9,
    pais_anfitrion: false
  });
  print("Equipo 'ITA' insertado exitosamente cumpliendo $jsonSchema.");
} catch (e) {
  print("Aviso: El equipo 'ITA' ya existía o fue insertado previamente.");
}
printjson(db.equipos.findOne({ codigo_iso: "ITA" }));

print("\n==================================================");
print(" 2. DEMOSTRACIÓN DE VALIDACIÓN ESTRICTA (RECHAZO)");
print("==================================================");
try {
  // Intento de inserción con dorsal inválido (> 99) para probar el validador
  db.jugadores.insertOne({
    _id: "ERR-999",
    nombre: "Jugador Inválido",
    dorsal: 150, // Inválido según esquema: máximo 99
    posicion: "DEL",
    codigo_equipo: "ARG"
  });
  print("ADVERTENCIA: El documento no debió insertarse.");
} catch (e) {
  print("ÉXITO: El motor MongoDB rechazó el documento por violación de esquema ($jsonSchema):");
  print("  -> " + e.message);
}

print("\n==================================================");
print(" 3. INSERCIÓN DE NUEVO JUGADOR (VALIDADO)");
print("==================================================");
try {
  db.jugadores.insertOne({
    _id: "ARG-24",
    nombre: "Martin Solari",
    dorsal: 24,
    posicion: "DEL",
    fecha_nacimiento: "2003-05-14",
    altura_cm: 180,
    pie_habil: "derecho",
    codigo_equipo: "ARG",
    equipo_id: "ARG",
    estado: "Convocado",
    estadisticas: { partidos: 0, goles: 0, asistencias: 0 }
  });
  print("Jugador 'ARG-24' insertado exitosamente cumpliendo $jsonSchema.");
} catch (e) {
  print("Aviso: El jugador ARG-24 ya existía en la base.");
}
printjson(db.jugadores.findOne({ _id: "ARG-24" }));

print("\n==================================================");
print(" 4. ACTUALIZACIÓN CONTROLADA DE EQUIPO ($set)");
print("==================================================");
// Actualiza director técnico y confirma atributo con $set
db.equipos.updateOne(
  { codigo_iso: "ARG" },
  {
    $set: {
      director_tecnico: "Lionel Scaloni",
      pais_anfitrion: true
    }
  }
);
print("Equipo ARG actualizado con $set:");
printjson(db.equipos.findOne({ codigo_iso: "ARG" }));

print("\n==================================================");
print(" 5. ACTUALIZACIÓN CONTROLADA DE JUGADOR ($set e $inc)");
print("==================================================");
// Actualiza estado y club con $set, e incrementa partidos y goles con $inc sin afectar relaciones
db.jugadores.updateOne(
  { _id: "ARG-24" },
  {
    $set: {
      club_actual: "Inter Miami",
      estado: "Convocado"
    },
    $inc: {
      "estadisticas.partidos": 1,
      "estadisticas.goles": 1
    }
  }
);
print("Jugador ARG-24 actualizado:");
printjson(db.jugadores.findOne(
  { _id: "ARG-24" },
  { nombre: 1, codigo_equipo: 1, estado: 1, club_actual: 1, estadisticas: 1 }
));


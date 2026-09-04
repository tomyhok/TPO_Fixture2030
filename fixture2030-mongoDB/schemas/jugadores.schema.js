// schemas/jugadores.schema.js — Reglas de validación estricta para la colección jugadores (RF3, RF7)
// Define la colección utilizando únicamente db.createCollection con $jsonSchema

db.createCollection("jugadores", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["nombre", "dorsal", "posicion", "codigo_equipo"],
      properties: {
        _id: {
          bsonType: "string",
          description: "Identificador único del jugador en formato EQUIPO-DORSAL (ej. 'ARG-10')"
        },
        nombre: {
          bsonType: "string",
          description: "Nombre y apellido del jugador (obligatorio)"
        },
        nombre_completo: {
          bsonType: "string",
          description: "Nombre completo alternativo del jugador"
        },
        dorsal: {
          bsonType: "int",
          minimum: 1,
          maximum: 99,
          description: "Número de dorsal oficial entre 1 y 99 (obligatorio)"
        },
        posicion: {
          enum: ["ARQ", "DEF", "MED", "DEL", "Arquero", "Defensor", "Mediocampista", "Delantero"],
          description: "Posición táctica en el campo de juego (obligatorio)"
        },
        fecha_nacimiento: {
          bsonType: "string",
          description: "Fecha de nacimiento en formato YYYY-MM-DD"
        },
        edad: {
          bsonType: "int",
          description: "Edad actual del jugador"
        },
        altura_cm: {
          bsonType: "int",
          minimum: 150,
          maximum: 220,
          description: "Estatura del jugador en centímetros"
        },
        pie_habil: {
          enum: ["derecho", "izquierdo", "ambidiestro"],
          description: "Pie hábil preferido del futbolista"
        },
        codigo_equipo: {
          bsonType: "string",
          minLength: 3,
          maxLength: 3,
          description: "Clave foránea hacia equipos.codigo_iso (obligatorio, ej. 'ARG')"
        },
        equipo_id: {
          bsonType: "string",
          minLength: 3,
          maxLength: 3,
          description: "Referencia compatible con equipos._id"
        },
        estado: {
          enum: ["Convocado", "Lesionado", "Suspendido"],
          description: "Estado de convocatoria médica o disciplinaria"
        },
        club_actual: {
          bsonType: "string",
          description: "Club actual de procedencia del futbolista"
        },
        estadisticas: {
          bsonType: "object",
          description: "Subdocumento embebido con estadísticas deportivas del jugador",
          properties: {
            partidos: { bsonType: "int", minimum: 0 },
            goles: { bsonType: "int", minimum: 0 },
            asistencias: { bsonType: "int", minimum: 0 }
          }
        },
        estadisticas_historicas: {
          bsonType: "object",
          description: "Subdocumento de métricas históricas"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
// schemas/jugadores.schema.js — Reglas de validación estricta para la colección jugadores (RF3, RF7)
// Define la colección utilizando únicamente db.createCollection con $jsonSchema

db.createCollection("jugadores", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      additionalProperties: false,
      required: ["nombre", "dorsal", "posicion", "fecha_nacimiento", "edad", "altura_cm", "pie_habil", "club_actual", "codigo_equipo"],
      properties: {
        _id: {
          bsonType: "string",
          description: "Identificador único del jugador en formato EQUIPO-DORSAL (ej. 'ARG-10')"
        },
        nombre: {
          bsonType: "string",
          description: "Nombre y apellido del jugador (obligatorio)"
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
        club_actual: {
          bsonType: "string",
          description: "Club actual de procedencia del futbolista"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
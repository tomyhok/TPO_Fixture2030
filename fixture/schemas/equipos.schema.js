// schemas/equipos.schema.js — Reglas de validación estricta para la colección equipos (RF3, RF7)
// Define la colección utilizando únicamente db.createCollection con $jsonSchema

db.createCollection("equipos", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["codigo_iso", "nombre", "confederacion", "grupo", "ranking_fifa"],
      properties: {
        _id: {
          bsonType: "string",
          description: "Identificador único de la selección (código FIFA/ISO, ej. 'ARG')"
        },
        codigo_iso: {
          bsonType: "string",
          minLength: 3,
          maxLength: 3,
          description: "Código ISO-3 del país participante (obligatorio, ej. 'ARG')"
        },
        nombre: {
          bsonType: "string",
          description: "Nombre oficial de la selección nacional (obligatorio)"
        },
        confederacion: {
          enum: ["CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"],
          description: "Confederación oficial de fútbol válida (obligatorio)"
        },
        grupo: {
          enum: ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P"],
          description: "Grupo asignado para el Mundial 2030 (A a P, obligatorio)"
        },
        director_tecnico: {
          bsonType: "string",
          description: "Nombre del Director Técnico de la selección"
        },
        ranking_fifa: {
          bsonType: "int",
          minimum: 1,
          description: "Posición en el ranking oficial de la FIFA (obligatorio)"
        },
        pais_anfitrion: {
          bsonType: "bool",
          description: "Indica si la selección es país anfitrión del torneo"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

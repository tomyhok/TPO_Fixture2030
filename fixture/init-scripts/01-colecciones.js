// 01-colecciones.js — crea las colecciones con sus reglas de validación (RF3, RF7)
// Se ejecuta automáticamente al levantar el contenedor por primera vez.

print("=== Creando colecciones con esquemas de validación estricta ===");

load("/schemas/equipos.schema.js");
print("Colección 'equipos' creada exitosamente con validación $jsonSchema.");

load("/schemas/jugadores.schema.js");
print("Colección 'jugadores' creada exitosamente con validación $jsonSchema.");


// 04-explain.js — Análisis de rendimiento con explain(): Comparativa Antes vs. Después del índice (RF13, RNF4)
// Uso: mongosh fixture2030 --file /queries/04-explain.js

function extraerEtapaEIndice(plan) {
  if (!plan) return { stage: "DESCONOCIDO", indexName: "N/A" };
  if (plan.stage === "IXSCAN") {
    return { stage: "IXSCAN", indexName: plan.indexName || "N/A" };
  }
  if (plan.stage === "COLLSCAN") {
    return { stage: "COLLSCAN", indexName: "ninguno (Full Collection Scan)" };
  }
  if (plan.inputStage) {
    return extraerEtapaEIndice(plan.inputStage);
  }
  return { stage: plan.stage, indexName: "N/A" };
}

function imprimirMetricas(etiqueta, explainResult) {
  const stats = explainResult.executionStats;
  const info = extraerEtapaEIndice(explainResult.queryPlanner.winningPlan);

  print(etiqueta);
  print("  ├─ Etapa de ejecución:   " + info.stage);
  print("  ├─ Índice utilizado:     " + info.indexName);
  print("  ├─ Documentos devueltos: " + stats.nReturned);
  print("  ├─ Documentos examinados:" + stats.totalDocsExamined);
  print("  ├─ Claves examinadas:    " + stats.totalKeysExamined);
  print("  └─ Tiempo de ejecución:  " + stats.executionTimeMillis + " ms");
}

print("================================================================================");
print(" EXPERIMENTO DE RENDIMIENTO: CONSULTA CRÍTICA ANTES Y DESPUÉS DEL ÍNDICE");
print("================================================================================");
print("Consulta analizada: Filtrar defensores de un equipo:");
print("  db.jugadores.find({ codigo_equipo: 'BRA', posicion: 'DEF' })\n");

// PASO 1: Análisis ANTES del índice (Eliminamos temporalmente el índice compuesto si existe)
try {
  db.jugadores.dropIndex("idx_equipo_posicion");
} catch (e) {
  // Si no existía, continuamos
}

const explainAntes = db.jugadores
  .find({ codigo_equipo: "BRA", posicion: "DEF" })
  .explain("executionStats");

imprimirMetricas(">>> ESTADO 1: ANTES de crear el índice (COLLSCAN)", explainAntes);

// PASO 2: Creación del índice
print("\n>>> CREANDO ÍNDICE: db.jugadores.createIndex({ codigo_equipo: 1, posicion: 1 }, { name: 'idx_equipo_posicion' })...");
db.jugadores.createIndex({ codigo_equipo: 1, posicion: 1 }, { name: "idx_equipo_posicion" });
print("Índice creado exitosamente.\n");

// PASO 3: Análisis DESPUÉS del índice
const explainDespues = db.jugadores
  .find({ codigo_equipo: "BRA", posicion: "DEF" })
  .explain("executionStats");

imprimirMetricas(">>> ESTADO 2: DESPUÉS de crear el índice (IXSCAN)", explainDespues);

print("\n--------------------------------------------------------------------------------");
print(" TABLA COMPARATIVA DE EFICIENCIA (RNF4):");
print("--------------------------------------------------------------------------------");
print(" Métrica                | Antes (Sin Índice)          | Después (Con Índice)");
print("------------------------|-----------------------------|-------------------------");
print(" Etapa de escaneo       | COLLSCAN (Barrido total)    | IXSCAN + FETCH (B-Tree)");
print(" Documentos examinados  | " + explainAntes.executionStats.totalDocsExamined + " documentos            | " + explainDespues.executionStats.totalDocsExamined + " documentos (Ratio 1:1)");
print(" Claves examinadas      | " + explainAntes.executionStats.totalKeysExamined + "                           | " + explainDespues.executionStats.totalKeysExamined);
print(" Complejidad temporal   | O(N)                        | O(log N)");
print("--------------------------------------------------------------------------------\n");


print("================================================================================");
print(" VERIFICACIÓN DE OTRAS CONSULTAS DEL MÓDULO CON SUS ÍNDICES RESPECTIVOS");
print("================================================================================");

imprimirMetricas(
  "1. Equipos por codigo_iso (Índice único idx_codigo_iso_unico):",
  db.equipos.find({ codigo_iso: "ARG" }).explain("executionStats")
);
print("");

imprimirMetricas(
  "2. Equipos del grupo A (Índice idx_grupo):",
  db.equipos.find({ grupo: "A" }).explain("executionStats")
);
print("");

imprimirMetricas(
  "3. Top 10 goleadores (Índice idx_goles):",
  db.jugadores.find({}).sort({ "estadisticas.goles": -1 }).limit(10).explain("executionStats")
);
print("");

imprimirMetricas(
  "4. Paginación de equipos por ranking (Índice idx_ranking):",
  db.equipos.find({}).sort({ ranking_fifa: 1 }).skip(10).limit(10).explain("executionStats")
);


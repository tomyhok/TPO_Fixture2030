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
  .hint({ $natural: 1 })
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
print(" Etapa de escaneo       | " + extraerEtapaEIndice(explainAntes.queryPlanner.winningPlan).stage + "                  | " + extraerEtapaEIndice(explainDespues.queryPlanner.winningPlan).stage);
print(" Documentos examinados  | " + explainAntes.executionStats.totalDocsExamined + " documentos            | " + explainDespues.executionStats.totalDocsExamined + " documentos");
print(" Claves examinadas      | " + explainAntes.executionStats.totalKeysExamined + "                           | " + explainDespues.executionStats.totalKeysExamined);
print(" Documentos devueltos    | " + explainAntes.executionStats.nReturned + "                           | " + explainDespues.executionStats.nReturned);
print(" Tiempo observado (ms)   | " + explainAntes.executionStats.executionTimeMillis + "                           | " + explainDespues.executionStats.executionTimeMillis);
print("--------------------------------------------------------------------------------\n");


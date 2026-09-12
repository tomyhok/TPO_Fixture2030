-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos
-- 06-medicion.cql : verificacion, distribucion y evidencia (RF12, RF13, RNF9)
-- =====================================================================
-- Ejecutar DESPUES de la carga masiva (tools/carga_masiva.sh).
-- Los resultados se vuelcan en docs/evidencia.md junto con la fecha,
-- la version observada y los recursos del equipo.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- 1) Ambiente observado (RNF9 y nota 5 del enunciado: usar latest obliga
--    a registrar que version se probo realmente).
-- ---------------------------------------------------------------------
SHOW VERSION;
SELECT release_version, cluster_name, data_center, rack, host_id
FROM system.local;

-- ---------------------------------------------------------------------
-- 2) Volumen cargado
-- ---------------------------------------------------------------------
-- COUNT(*) sin clave de particion es un full scan: aceptable como evidencia
-- puntual del hito, jamas como consulta de la aplicacion.
-- Con 1.000.000 de filas puede fallar con ReadFailure o ReadTimeout,
-- sobre todo si todavia hay escrituras en curso. Que falle NO es un error
-- del modelo: es la demostracion practica de por que Cassandra no resuelve
-- agregaciones globales. Alternativas:
--   * reintentar con  cqlsh --request-timeout=600  y el nodo en reposo;
--   * usar la estimacion de nodetool, que no recorre los datos:
--       nodetool tablestats fixture2030.comentarios_por_partido
--         -> "Number of partitions (estimate)" y "Space used (live)"
SELECT COUNT(*) AS total_comentarios FROM comentarios_por_partido;
SELECT COUNT(*) AS total_historial   FROM comentarios_por_usuario;

-- ---------------------------------------------------------------------
-- 3) Distribucion entre particiones (RNF5)
-- token() expone en que punto del anillo cae cada particion: sirve para
-- mostrar que las claves no se concentran en una sola zona.
-- ---------------------------------------------------------------------
SELECT id_partido, ventana, shard, token(id_partido, ventana, shard) AS token_particion
FROM comentarios_por_partido
LIMIT 20;

-- Filas por particion de una ventana concreta: los 4 shards deberian quedar
-- con cantidades parecidas (+/- 5%). Si uno se dispara, el hash del productor
-- esta sesgado y hay que revisarlo.
-- La ventana de abajo pertenece al dataset masivo. Elegir cualquier otra con:
--   SELECT id_partido, ventana FROM comentarios_por_partido LIMIT 1;
SELECT id_partido, ventana, shard, COUNT(*) AS filas
FROM comentarios_por_partido
WHERE id_partido = 'P-002' AND ventana = '203006160120' AND shard IN (0,1,2,3)
GROUP BY id_partido, ventana, shard;

-- ---------------------------------------------------------------------
-- 4) Costo real de las consultas (tracing)
-- Compara Q1 (por clave de particion) contra la consulta por indice sin
-- clave de particion. Anotar en la evidencia el tiempo total y la cantidad
-- de SSTables y particiones tocadas en cada caso.
-- ---------------------------------------------------------------------
TRACING ON;

-- 4a) Lectura del muro por clave de particion: debe tocar 1 particion.
--     En la traza aparece "Executing single-partition query" una sola vez.
SELECT id_comentario, usuario_alias, texto
FROM comentarios_por_partido
WHERE id_partido = 'P-002' AND ventana = '203006160120' AND shard = 0
LIMIT 20;

-- 4b) Lectura por indice secundario sin clave de particion: scatter-gather.
--     En la traza aparece "Submitting range requests on N ranges" seguido de
--     muchas "Executing single-partition query", para el mismo LIMIT 20.
SELECT id_partido, id_comentario
FROM comentarios_por_partido
WHERE idioma = 'pt'
LIMIT 20;

TRACING OFF;

-- ---------------------------------------------------------------------
-- 5) Mediciones que NO se hacen desde CQL
-- ---------------------------------------------------------------------
-- Tamano de particion, tombstones y latencias por tabla (desde el host):
--   docker compose exec cassandra nodetool tablestats fixture2030.comentarios_por_partido
--   docker compose exec cassandra nodetool tablehistograms fixture2030 comentarios_por_partido
--   docker compose exec cassandra nodetool cfstats fixture2030
--   docker compose exec cassandra nodetool status
--
-- Prueba de escritura sostenida (RF12):
--   bash tools/benchmark_escritura.sh
-- =====================================================================

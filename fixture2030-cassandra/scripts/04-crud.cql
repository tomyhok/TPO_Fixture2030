-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos
-- 04-crud.cql : operaciones CREATE / READ / UPDATE / DELETE (RF8)
-- =====================================================================
-- Todas las operaciones trabajan sobre un comentario de prueba propio para
-- no alterar la muestra cargada en 03-carga-muestra.cql.
-- Comentario de prueba: 3abbfa67-e506-11f5-83e7-00000005f1c7
--   partido P-001, ventana 203006152017, shard 3, usuario U-1003.
--   El shard 3 es el que corresponde a U-1003 por crc32(id_usuario) % 4.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- C) CREATE
-- Un comentario nuevo se escribe en la tabla principal Y en la vista de
-- historial. Se usa un BATCH LOGGED porque es el caso legitimo del patron:
-- misma informacion logica replicada en varias tablas. No se usa BATCH para
-- agrupar escrituras de particiones no relacionadas (eso degrada el
-- coordinador y no aporta performance en Cassandra).
-- ---------------------------------------------------------------------
BEGIN BATCH
  INSERT INTO comentarios_por_partido (
      id_partido, ventana, shard, id_comentario, id_usuario, usuario_alias,
      equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en)
  VALUES ('P-001', '203006152017', 3, 3abbfa67-e506-11f5-83e7-00000005f1c7,
      'U-1003', 'tribuna_sur', 'ARG', 'Comentario de prueba del Hito 6',
      'es', 'publicado', 78, '2030-06-15 20:17:05+0000');

  INSERT INTO comentarios_por_usuario (
      id_usuario, periodo, id_comentario, id_partido, texto, estado_moderacion, creado_en)
  VALUES ('U-1003', '203006', 3abbfa67-e506-11f5-83e7-00000005f1c7,
      'P-001', 'Comentario de prueba del Hito 6', 'publicado', '2030-06-15 20:17:05+0000');
APPLY BATCH;

-- ---------------------------------------------------------------------
-- R) READ
-- Lectura puntual por clave primaria completa: toca una unica particion.
-- ---------------------------------------------------------------------
SELECT id_comentario, usuario_alias, texto, estado_moderacion, minuto_partido, creado_en
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152017'
  AND shard = 3
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- ---------------------------------------------------------------------
-- U) UPDATE
-- 1. Correccion del texto por parte del autor.
-- ---------------------------------------------------------------------
UPDATE comentarios_por_partido
SET texto = 'Comentario de prueba del Hito 6 (editado)'
WHERE id_partido = 'P-001'
  AND ventana = '203006152017'
  AND shard = 3
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- 2. La misma correccion en la vista duplicada: la coherencia entre tablas
--    la mantiene la aplicacion, no el motor (no hay JOIN ni FK en Cassandra).
UPDATE comentarios_por_usuario
SET texto = 'Comentario de prueba del Hito 6 (editado)'
WHERE id_usuario = 'U-1003'
  AND periodo = '203006'
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- 3. Moderacion: el comentario se marca en revision y entra en la cola.
--    La fila de la cola nace con el TTL por defecto de la tabla (7 dias).
UPDATE comentarios_por_partido
SET estado_moderacion = 'en_revision'
WHERE id_partido = 'P-001'
  AND ventana = '203006152017'
  AND shard = 3
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

INSERT INTO comentarios_en_revision (
    id_partido, estado_moderacion, id_comentario, id_usuario, texto, motivo, creado_en)
VALUES ('P-001', 'en_revision', 3abbfa67-e506-11f5-83e7-00000005f1c7,
    'U-1003', 'Comentario de prueba del Hito 6 (editado)', 'reporte_usuario',
    '2030-06-15 20:17:05+0000');

-- 4. Escritura condicional (LWT): solo publica si sigue en revision.
--    Paxos cuesta ~4 viajes de red; se usa solo en el flujo de moderacion,
--    que es de bajo volumen, nunca en la escritura masiva de comentarios.
UPDATE comentarios_por_partido
SET estado_moderacion = 'publicado'
WHERE id_partido = 'P-001'
  AND ventana = '203006152017'
  AND shard = 3
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7
IF estado_moderacion = 'en_revision';

-- 5. Metricas de interaccion: los counter solo admiten UPDATE incremental.
UPDATE metricas_comentario
SET likes = likes + 1, respuestas = respuestas + 1
WHERE id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

SELECT * FROM metricas_comentario
WHERE id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- ---------------------------------------------------------------------
-- D) DELETE
-- Cada DELETE genera un tombstone que sobrevive gc_grace_seconds antes de
-- ser recolectado. Por eso el borrado siempre se hace por clave primaria
-- completa (un tombstone de celda/fila) y nunca por rango amplio.
-- ---------------------------------------------------------------------
-- 1. Resolver el caso de moderacion: se saca de la cola.
DELETE FROM comentarios_en_revision
WHERE id_partido = 'P-001'
  AND estado_moderacion = 'en_revision'
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- 2. Baja definitiva del comentario en las dos vistas.
BEGIN BATCH
  DELETE FROM comentarios_por_partido
  WHERE id_partido = 'P-001'
    AND ventana = '203006152017'
    AND shard = 3
    AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

  DELETE FROM comentarios_por_usuario
  WHERE id_usuario = 'U-1003'
    AND periodo = '203006'
    AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;
APPLY BATCH;

-- 3. Los counter se borran aparte. Un counter borrado NO debe volver a
--    incrementarse: Cassandra no garantiza el valor luego de reutilizar la
--    clave. Se acepta porque el id_comentario es un timeuuid irrepetible.
DELETE FROM metricas_comentario
WHERE id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

-- 4. Verificacion: la lectura debe devolver 0 filas.
SELECT COUNT(*) AS debe_ser_cero
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152017'
  AND shard = 3
  AND id_comentario = 3abbfa67-e506-11f5-83e7-00000005f1c7;

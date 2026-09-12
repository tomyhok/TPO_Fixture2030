-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos
-- 05-consultas.cql : consultas de lectura del modulo (RF9, RF10)
-- =====================================================================
-- Todas las consultas usan condiciones compatibles con la clave primaria.
-- Ninguna consulta del flujo productivo usa ALLOW FILTERING; los dos casos
-- que aparecen al final estan marcados como contraejemplo medido.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- Q1 - MURO EN VIVO (consulta principal del modulo)
-- "Ultimos 20 comentarios del partido P-001 en el minuto 20:15."
-- Entrada: id_partido, ventana, shard.  Orden: id_comentario DESC.
-- Costo: 1 particion por shard. La aplicacion lanza los 4 shards en
-- paralelo y hace el merge por id_comentario (k-way merge de 4 listas ya
-- ordenadas). Se aceptan 4 lecturas chicas en vez de 1 particion caliente.
-- ---------------------------------------------------------------------
SELECT id_comentario, usuario_alias, equipo_apoyado, texto, minuto_partido, creado_en
FROM comentarios_por_partido
WHERE id_partido = 'P-001' AND ventana = '203006152015' AND shard = 0
LIMIT 20;

-- Los 4 shards de la misma ventana en una sola sentencia (IN sobre la
-- ultima columna de la clave de particion). Comodo para cqlsh; en la
-- aplicacion conviene igual disparar 4 consultas asincronas, porque el IN
-- concentra el trabajo de merge en el nodo coordinador.
SELECT shard, id_comentario, usuario_alias, texto
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152015'
  AND shard IN (0, 1, 2, 3)
LIMIT 40;

-- ---------------------------------------------------------------------
-- Q1b - SCROLL HACIA ATRAS dentro de una ventana (paginado por clustering)
-- "Seguir leyendo el muro desde el ultimo comentario ya mostrado."
-- El filtro por rango de clustering evita OFFSET (que Cassandra no tiene).
-- ---------------------------------------------------------------------
SELECT id_comentario, usuario_alias, texto
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152015'
  AND shard = 1
  AND id_comentario < 0a745805-e506-11f5-8005-00000005f1c7
LIMIT 10;

-- Rango temporal dentro de la ventana usando las funciones de timeuuid:
-- recupera lo publicado entre dos instantes sin columna adicional.
SELECT id_comentario, creado_en, usuario_alias, texto
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152016'
  AND shard = 3
  AND id_comentario >= minTimeuuid('2030-06-15 20:16:00+0000')
  AND id_comentario <  maxTimeuuid('2030-06-15 20:17:00+0000');

-- ---------------------------------------------------------------------
-- Q2 - HISTORIAL POR USUARIO (resuelto por la tabla duplicada, RF10)
-- "Ultimos comentarios del usuario U-1002 en junio de 2030."
-- Entrada: id_usuario, periodo.  Orden: mas reciente primero.  Costo: 1 particion.
-- ---------------------------------------------------------------------
SELECT id_comentario, id_partido, estado_moderacion, texto, creado_en
FROM comentarios_por_usuario
WHERE id_usuario = 'U-1002' AND periodo = '203006'
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q3 - COLA DE MODERACION
-- "Comentarios pendientes de revision del partido P-001, por orden de llegada."
-- Entrada: id_partido, estado_moderacion.  Orden: id_comentario ASC.
-- ---------------------------------------------------------------------
SELECT id_comentario, id_usuario, motivo, texto, creado_en
FROM comentarios_en_revision
WHERE id_partido = 'P-001' AND estado_moderacion = 'en_revision'
LIMIT 50;

-- Cuanto le queda de vida a cada fila de la cola (TTL efectivo, en segundos).
SELECT id_comentario, TTL(texto) AS ttl_restante_seg
FROM comentarios_en_revision
WHERE id_partido = 'P-001' AND estado_moderacion = 'en_revision';

-- ---------------------------------------------------------------------
-- Q4 - METRICAS DE INTERACCION
-- "Likes, reportes y respuestas de un comentario." Costo: 1 particion.
-- ---------------------------------------------------------------------
SELECT id_comentario, likes, reportes, respuestas
FROM metricas_comentario
WHERE id_comentario = f03a7a01-e505-11f5-8001-00000005f1c7;

-- Varias tarjetas del muro de una vez (el cliente ya conoce los ids por Q1).
SELECT id_comentario, likes, reportes
FROM metricas_comentario
WHERE id_comentario IN (
  f03a7a01-e505-11f5-8001-00000005f1c7,
  f6c8f182-e505-11f5-8002-00000005f1c7,
  fd576903-e505-11f5-8003-00000005f1c7);

-- ---------------------------------------------------------------------
-- Q5 - ESTRUCTURA SECUNDARIA: indice local por idioma (RF10, comparativa)
-- ---------------------------------------------------------------------
-- 5a) USO RECOMENDADO: el indice se combina con la clave de particion.
--     La lectura sigue tocando una sola particion y el indice solo filtra
--     dentro de ella. Es el unico caso en que un indice local escala.
SELECT id_comentario, idioma, usuario_alias, texto
FROM comentarios_por_partido
WHERE id_partido = 'P-001'
  AND ventana = '203006152015'
  AND shard = 1
  AND idioma = 'pt';
-- Nota: segun la version de Cassandra esta consulta puede pedir
-- ALLOW FILTERING al combinar indice y clave de particion. Agregarlo en ese
-- caso NO cambia el costo: el filtrado sigue acotado a una sola particion.

-- 5b) USO DESACONSEJADO: sin clave de particion, el coordinador consulta
--     todos los nodos que tienen datos (scatter-gather) y el tiempo de
--     respuesta crece con el tamano del cluster, no con el del resultado.
--     Funciona en el laboratorio de un nodo y se rompe en produccion.
--     Medir la diferencia con TRACING ON antes y despues (ver 06-medicion.cql).
SELECT id_partido, ventana, id_comentario, idioma
FROM comentarios_por_partido
WHERE idioma = 'pt'
LIMIT 20;

-- ---------------------------------------------------------------------
-- CONTRAEJEMPLO DOCUMENTADO (no usar en la aplicacion)
-- Filtrar por estado sin clave de particion obliga a ALLOW FILTERING:
-- Cassandra lee y descarta filas en todo el rango de tokens. Este es
-- exactamente el motivo por el que existe la tabla comentarios_en_revision.
-- ---------------------------------------------------------------------
-- SELECT * FROM comentarios_por_partido
-- WHERE estado_moderacion = 'en_revision' ALLOW FILTERING;

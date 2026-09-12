-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos
-- 02-tablas.cql : definicion del modelo tabular (RF4, RF5, RF6, RF7, RF10)
-- =====================================================================
-- Cada tabla existe por UNA consulta concreta del modulo (RNF4). El detalle
-- completo del razonamiento esta en docs/modelo_tabular.md.
--
-- Convenciones de particionado usadas en todo el modulo:
--   ventana : texto 'AAAAMMDDHHMM' -> bucket temporal de 1 minuto.
--   shard   : entero 0..3 -> sub-particion sintetica dentro de la ventana.
--             shard = crc32(id_usuario) % 4   (lo calcula el productor, ver tools/).
-- Ver docs/analisis_hito6.md apartado 4 para los supuestos de carga.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- TABLA 1 (principal): comentarios_por_partido
-- Consulta que la motiva (Q1):
--   "Traer los ultimos N comentarios publicados de un partido, del mas
--    reciente al mas viejo, mientras el partido se esta jugando."
--
-- Clave primaria: ((id_partido, ventana, shard), id_comentario)
--   - Clave de particion (id_partido, ventana, shard):
--       * id_partido  -> aisla el trafico de cada encuentro.
--       * ventana     -> corta la particion cada minuto, evitando la
--                        particion ilimitada de un partido de 2 horas.
--       * shard       -> reparte la escritura simultanea de un minuto
--                        entre 4 particiones distintas (anti-hotspot).
--   - Clustering (id_comentario timeuuid DESC):
--       * ordena por instante de creacion descendente sin columna extra
--         y desempata con unicidad, porque el timeuuid lleva el timestamp
--         embebido. Es exactamente el orden de lectura del muro en vivo.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios_por_partido (
    id_partido        text,        -- 'P-001' (homologado con Neo4j/MongoDB)
    ventana           text,        -- 'AAAAMMDDHHMM' - bucket de 1 minuto
    shard             int,         -- 0..3
    id_comentario     timeuuid,    -- identidad + orden temporal
    id_usuario        text,        -- autor (referencia logica)
    usuario_alias     text,        -- alias desnormalizado para render directo
    equipo_apoyado    text,        -- codigo ISO del equipo ('ARG', 'BRA')
    texto             text,        -- contenido del comentario
    idioma            text,        -- 'es', 'pt', 'en'
    estado_moderacion text,        -- publicado | en_revision | rechazado
    minuto_partido    int,         -- contexto deportivo: minuto de juego
    creado_en         timestamp,   -- redundante con el timeuuid, legible
    PRIMARY KEY ((id_partido, ventana, shard), id_comentario)
) WITH CLUSTERING ORDER BY (id_comentario DESC)
  AND comment = 'Muro en vivo por partido. Bucket de 1 min + 4 shards.'
  -- Serie temporal de escritura intensiva: TWCS compacta por ventana y
  -- permite descartar SSTables completas cuando el dato envejece.
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': 1
  }
  -- Los comentarios se leen una sola vez en vivo: no conviene gastar RAM.
  AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'}
  AND default_time_to_live = 0;

-- ---------------------------------------------------------------------
-- TABLA 2 (acceso secundario por duplicacion controlada): comentarios_por_usuario
-- Consulta que la motiva (Q2):
--   "Mostrar el historial de comentarios de un usuario en el mes actual."
--
-- Por que NO se resuelve con la tabla 1: id_usuario no forma parte de su
-- clave de particion, de modo que la consulta obligaria a un ALLOW FILTERING
-- que recorre todas las particiones del torneo. Se acepta duplicar la fila
-- (RF10): el costo es una escritura extra por comentario, contra un scatter
-- gather sobre todo el cluster en cada lectura de perfil.
--
-- Clave primaria: ((id_usuario, periodo), id_comentario)
--   - periodo 'AAAAMM' acota la particion del usuario a un mes de actividad.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios_por_usuario (
    id_usuario        text,
    periodo           text,        -- 'AAAAMM'
    id_comentario     timeuuid,
    id_partido        text,
    texto             text,
    estado_moderacion text,
    creado_en         timestamp,
    PRIMARY KEY ((id_usuario, periodo), id_comentario)
) WITH CLUSTERING ORDER BY (id_comentario DESC)
  AND comment = 'Historial por usuario. Vista duplicada de comentarios_por_partido.';

-- ---------------------------------------------------------------------
-- TABLA 3 (cola operativa): comentarios_en_revision
-- Consulta que la motiva (Q3):
--   "Listar los comentarios pendientes de moderacion de un partido, del mas
--    viejo al mas nuevo, para atenderlos por orden de llegada."
--
-- Solo se escriben aca los estados NO publicados ('en_revision', 'rechazado'),
-- por lo que la particion se mantiene chica aunque el partido sea masivo.
-- La fila se borra cuando el moderador resuelve el caso; el TTL de 7 dias es
-- la red de seguridad para que una cola abandonada no crezca sin limite.
-- Costo aceptado: tombstones acotados, discutidos en docs/decisiones -> TTL.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios_en_revision (
    id_partido        text,
    estado_moderacion text,
    id_comentario     timeuuid,
    id_usuario        text,
    texto             text,
    motivo            text,        -- 'reporte_usuario' | 'filtro_automatico'
    creado_en         timestamp,
    PRIMARY KEY ((id_partido, estado_moderacion), id_comentario)
) WITH CLUSTERING ORDER BY (id_comentario ASC)
  AND default_time_to_live = 604800      -- 7 dias
  AND gc_grace_seconds = 86400           -- 1 dia: nodo unico, sin hinted handoff largo
  AND comment = 'Cola de moderacion. Solo estados distintos de publicado.';

-- ---------------------------------------------------------------------
-- TABLA 4 (metricas de interaccion): metricas_comentario
-- Consulta que la motiva (Q4):
--   "Cuantos likes y reportes acumula un comentario."
--
-- Las columnas counter no pueden convivir con columnas normales en la misma
-- tabla, y ademas un like es un incremento concurrente, no un UPDATE de fila.
-- Por eso las metricas viven aparte (RF6).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metricas_comentario (
    id_comentario timeuuid PRIMARY KEY,
    likes         counter,
    reportes      counter,
    respuestas    counter
) WITH comment = 'Contadores de interaccion por comentario.';

-- ---------------------------------------------------------------------
-- ESTRUCTURA SECUNDARIA ALTERNATIVA (comparativa, RF10)
-- Indice secundario local sobre el idioma del comentario.
-- Se crea para poder DEMOSTRAR y MEDIR el trade-off, no como solucion
-- recomendada: un indice local obliga a consultar todos los nodos que
-- poseen particiones (scatter-gather) salvo que la consulta tambien fije
-- la clave de particion. Ver la comparacion en 05-consultas.cql.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_idioma_comentario
    ON comentarios_por_partido (idioma);

DESCRIBE TABLES;

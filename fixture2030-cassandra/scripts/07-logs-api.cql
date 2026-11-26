-- =====================================================================
-- Fixture 2030 - Persistencia de Logs Operativos de la API en Cassandra
-- 07-logs-api.cql : modelo tabular guiado por consultas (Ing. de Datos II)
-- =====================================================================
-- Cada tabla responde a una consulta operativa concreta sin usar
-- ALLOW FILTERING ni indices secundarios globales/locales sobre alta
-- cardinalidad, evitando scatter-gather sobre el anillo.
--
-- Estrategia de compactacion y ciclo de vida:
--   * TimeWindowCompactionStrategy (TWCS) con ventanas de 1 dia: agrupa
--     SSTables por periodo y permite eliminar SSTables vencidas completas
--     sin amplificacion de compactacion cuando expira el TTL.
--   * default_time_to_live = 2592000 (30 dias) para retencion acotada.
--   * gc_grace_seconds = 86400 (1 dia), adecuado al laboratorio de nodo
--     unico para evitar acumulacion prolongada de tombstones.
-- =====================================================================

USE fixture2030;

-- ---------------------------------------------------------------------
-- TABLA 1 (Q1): logs_api_por_hora
-- Consulta que la motiva:
--   "Listar los ultimos N logs emitidos por un servicio en una ventana
--    horaria UTC (AAAAMMDDHH), ordenados del mas reciente al mas viejo."
--
-- Clave primaria: ((servicio, ventana_hora), id_log)
--   - servicio + ventana_hora acotan el tamano de cada particion a 1 hora
--     de trafico, evitando particiones ilimitadas (wide partitions).
--   - id_log (timeuuid DESC) ordena de mas reciente a mas antiguo y
--     garantiza unicidad entre eventos concurrentes dentro del mismo ms.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_api_por_hora (
    servicio      text,
    ventana_hora  text,        -- 'AAAAMMDDHH' (UTC)
    id_log        timeuuid,
    creado_en     timestamp,
    nivel         text,        -- DEBUG | INFO | WARNING | ERROR | CRITICAL
    logger        text,        -- fixture2030.acceso | fixture2030.adaptador | ...
    request_id    text,
    metodo        text,
    ruta          text,
    status_http   int,
    dependencia   text,
    operacion     text,
    resultado     text,
    duracion_ms   double,
    mensaje       text,
    instancia     text,
    PRIMARY KEY ((servicio, ventana_hora), id_log)
) WITH CLUSTERING ORDER BY (id_log DESC)
  AND comment = 'Timeline operativo de logs de la API por ventana horaria UTC.'
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  }
  AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'}
  AND default_time_to_live = 2592000
  AND gc_grace_seconds = 86400;

-- ---------------------------------------------------------------------
-- TABLA 2 (Q2): logs_api_por_request
-- Consulta que la motiva:
--   "Reconstruir la traza completa de un X-Request-ID en orden
--    cronologico de ejecucion (middleware + adaptadores + errores)."
--
-- Clave primaria: ((request_id), id_log)
--   - Solo se escribe cuando request_id != '-' y no esta vacio.
--   - id_log (timeuuid ASC) entrega los pasos en orden de ocurrencia.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_api_por_request (
    request_id    text,
    id_log        timeuuid,
    creado_en     timestamp,
    servicio      text,
    nivel         text,
    logger        text,
    metodo        text,
    ruta          text,
    status_http   int,
    dependencia   text,
    operacion     text,
    resultado     text,
    duracion_ms   double,
    mensaje       text,
    instancia     text,
    PRIMARY KEY ((request_id), id_log)
) WITH CLUSTERING ORDER BY (id_log ASC)
  AND comment = 'Traza distribuida por X-Request-ID en orden cronologico.'
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  }
  AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'}
  AND default_time_to_live = 2592000
  AND gc_grace_seconds = 86400;

-- ---------------------------------------------------------------------
-- TABLA 3 (Q3): logs_api_por_nivel
-- Consulta que la motiva:
--   "Consultar los incidentes (WARNING, ERROR, CRITICAL) ocurridos en
--    una fecha UTC (AAAAMMDD), del mas reciente al mas viejo."
--
-- Desnormalizacion selectiva (sparse table):
--   - Solo se escriben eventos con nivel in ('WARNING', 'ERROR', 'CRITICAL').
--   - Evita amplificacion de escritura sobre el trafico normal INFO.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logs_api_por_nivel (
    nivel         text,        -- WARNING | ERROR | CRITICAL
    fecha         text,        -- 'AAAAMMDD' (UTC)
    id_log        timeuuid,
    creado_en     timestamp,
    servicio      text,
    logger        text,
    request_id    text,
    metodo        text,
    ruta          text,
    status_http   int,
    dependencia   text,
    operacion     text,
    resultado     text,
    duracion_ms   double,
    mensaje       text,
    instancia     text,
    PRIMARY KEY ((nivel, fecha), id_log)
) WITH CLUSTERING ORDER BY (id_log DESC)
  AND comment = 'Incidentes WARNING/ERROR/CRITICAL por dia (tabla dispersa).'
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  }
  AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'}
  AND default_time_to_live = 2592000
  AND gc_grace_seconds = 86400;

DESCRIBE TABLES;

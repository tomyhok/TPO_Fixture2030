-- =====================================================================
-- Hito 6 - Fixture 2030 - Modulo de Comentarios Masivos (Apache Cassandra)
-- 01-keyspace.cql : creacion del keyspace (RF2)
-- =====================================================================
-- Estrategia: SimpleStrategy con RF=1 porque el laboratorio corre sobre un
-- unico nodo en la notebook del equipo. Con un solo nodo no existe otro juego
-- de replicas donde ubicar copias, por lo que cualquier RF>1 quedaria en
-- estado UNAVAILABLE en las escrituras con consistencia QUORUM.
--
-- Diferencia con produccion (ver docs/analisis_hito6.md, apartado 4):
-- un despliegue real del Fixture 2030 usaria NetworkTopologyStrategy con
-- RF=3 por datacenter, escrituras LOCAL_QUORUM y al menos un DC por region
-- (AMS, EUR, ASIA) para acercar la latencia de escritura al hincha.
-- =====================================================================

-- IF NOT EXISTS garantiza idempotencia (RNF7): el script puede reejecutarse.
CREATE KEYSPACE IF NOT EXISTS fixture2030
WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 1
}
AND durable_writes = true;

USE fixture2030;

-- Verificacion rapida del keyspace creado.
DESCRIBE KEYSPACE fixture2030;

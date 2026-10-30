"""
Hito 12 - Fixture 2030 - Funciones compartidas por los scripts.

Conexiones, constantes del escenario y las dos formas de leer el muro
(directo de Cassandra = linea base, Redis = optimizado).
"""

import json
import os
import zlib
from datetime import datetime, timedelta, timezone

import redis
from cassandra.cluster import Cluster

CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "127.0.0.1")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# Keyspace propio del hito: no se tocan los datos del Hito 6.
KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "fixture2030_carga")

SHARDS = 4               # misma formula de shard que el Hito 6
PARTIDOS = ["P-%03d" % i for i in range(1, 65)]
PARTIDO_CALIENTE = "P-001"
VENTANAS_MURO = 3        # el muro mira los ultimos 3 minutos
TAM_MURO = 20            # comentarios que devuelve una lectura
TAM_MURO_REDIS = 100     # comentarios que se guardan en Redis por partido
TTL_MURO = 60            # segundos; acota cuanto puede quedar desactualizado

CARPETA_RESULTADOS = os.path.join(
    os.path.dirname(__file__), "..", "docs", "evidencia", "resultados")


def conectar_cassandra(keyspace=KEYSPACE):
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    session = cluster.connect(keyspace)
    session.default_timeout = 2  # segundos; pasado eso cuenta como error
    return cluster, session


def conectar_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                       socket_timeout=2)


def shard_de(id_usuario):
    return zlib.crc32(id_usuario.encode()) % SHARDS


def ventana_de(momento):
    return momento.strftime("%Y%m%d%H%M")


def elegir_partido(rnd):
    """Clave caliente: la mitad del trafico va al partido P-001."""
    if rnd.random() < 0.5:
        return PARTIDO_CALIENTE
    return rnd.choice(PARTIDOS)


def elegir_usuario(rnd):
    """Los 5.000 usuarios mas activos generan ~30% de los comentarios."""
    if rnd.random() < 0.3:
        return "U-%06d" % rnd.randrange(5_000)
    return "U-%06d" % rnd.randrange(200_000)


def preparar_lectura(session):
    return session.prepare(
        "SELECT id_comentario, usuario_alias, texto, creado_en "
        "FROM comentarios_por_partido "
        "WHERE id_partido = ? AND ventana = ? AND shard = ? LIMIT %d" % TAM_MURO)


def leer_muro_cassandra(session, ps_lectura, partido, limite=TAM_MURO):
    """Linea base: 3 ventanas x 4 shards = 12 consultas, se unen y ordenan."""
    ahora = datetime.now(timezone.utc)
    futuros = []
    for m in range(VENTANAS_MURO):
        ventana = ventana_de(ahora - timedelta(minutes=m))
        for shard in range(SHARDS):
            futuros.append(session.execute_async(ps_lectura, (partido, ventana, shard)))
    filas = []
    for f in futuros:
        filas.extend(f.result())
    filas.sort(key=lambda fila: fila.id_comentario.time, reverse=True)
    return filas[:limite]


def a_json(id_comentario, alias, texto, creado_en):
    return json.dumps({"id": str(id_comentario), "alias": alias, "texto": texto,
                       "creado_en": creado_en.isoformat()})


def leer_muro_redis(r, session, ps_lectura, partido):
    """
    Optimizado: una sola lectura LRANGE.
    Si la lista no existe (miss), se arma desde Cassandra. Un lock con SET NX
    evita que varios hilos la reconstruyan a la vez y dupliquen elementos.
    Devuelve (comentarios, fue_hit).
    """
    clave = "muro:" + partido
    muro = r.lrange(clave, 0, TAM_MURO - 1)
    if muro:
        return muro, True

    filas = leer_muro_cassandra(session, ps_lectura, partido, TAM_MURO_REDIS)
    if filas and r.set("lock:" + clave, "1", nx=True, ex=2):
        pipe = r.pipeline()
        pipe.delete(clave)
        pipe.rpush(clave, *[a_json(f.id_comentario, f.usuario_alias, f.texto,
                                   f.creado_en) for f in filas])
        pipe.expire(clave, TTL_MURO)
        pipe.execute()
    return filas[:TAM_MURO], False

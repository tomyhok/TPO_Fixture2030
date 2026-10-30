"""
Hito 12 - PREPARACION: crea el keyspace de prueba y carga comentarios
historicos (partidos ya jugados) para que las tablas no esten vacias.

Uso:
    python scripts/preparar_datos.py --filas 100000 --semilla 2030

Es idempotente: con la misma semilla genera los mismos id_comentario, asi que
correrlo dos veces no duplica filas (el INSERT de Cassandra es un upsert).
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.util import uuid_from_time

import comun

DDL = [
    """CREATE KEYSPACE IF NOT EXISTS %s
       WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}""" % comun.KEYSPACE,
    # Mismo modelo que el Hito 6 (bucket de 1 minuto + 4 shards).
    """CREATE TABLE IF NOT EXISTS %s.comentarios_por_partido (
        id_partido text, ventana text, shard int, id_comentario timeuuid,
        id_usuario text, usuario_alias text, equipo_apoyado text, texto text,
        minuto_partido int, creado_en timestamp,
        PRIMARY KEY ((id_partido, ventana, shard), id_comentario)
    ) WITH CLUSTERING ORDER BY (id_comentario DESC)""" % comun.KEYSPACE,
    """CREATE TABLE IF NOT EXISTS %s.comentarios_por_usuario (
        id_usuario text, periodo text, id_comentario timeuuid, id_partido text,
        texto text, creado_en timestamp,
        PRIMARY KEY ((id_usuario, periodo), id_comentario)
    ) WITH CLUSTERING ORDER BY (id_comentario DESC)""" % comun.KEYSPACE,
]

EQUIPOS = ["ARG", "BRA", "URU", "ESP", "FRA", "ENG", "GER", "MEX", "POR", "MAR"]
FRASES = ["Que jugada, casi gol", "Golazo", "El VAR tarda demasiado",
          "Penal clarisimo", "Atajada tremenda", "Offside milimetrico"]
INICIO_TORNEO = datetime(2030, 6, 15, 18, 0, tzinfo=timezone.utc)


def generar(filas, semilla):
    rnd = random.Random(semilla)
    por_partido, por_usuario = [], []
    for n in range(filas):
        partido = comun.elegir_partido(rnd)
        usuario = comun.elegir_usuario(rnd)
        nro = int(partido[2:])
        minuto = rnd.randrange(120)
        momento = INICIO_TORNEO + timedelta(days=nro // 4, hours=3 * (nro % 4),
                                            minutes=minuto, seconds=rnd.randrange(60))
        # node=n hace el timeuuid unico y reproducible con la semilla.
        id_com = uuid_from_time(momento, node=n, clock_seq=0)
        texto = rnd.choice(FRASES)
        por_partido.append((partido, comun.ventana_de(momento), comun.shard_de(usuario),
                            id_com, usuario, "hincha_" + usuario[2:],
                            rnd.choice(EQUIPOS), texto, minuto, momento))
        por_usuario.append((usuario, momento.strftime("%Y%m"), id_com, partido,
                            texto, momento))
    return por_partido, por_usuario


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filas", type=int, default=100_000)
    ap.add_argument("--semilla", type=int, default=2030)
    args = ap.parse_args()

    cluster = Cluster([comun.CASSANDRA_HOST], port=comun.CASSANDRA_PORT)
    session = cluster.connect()
    for sentencia in DDL:
        session.execute(sentencia)
    session.set_keyspace(comun.KEYSPACE)

    print("Generando %d comentarios (semilla %d)..." % (args.filas, args.semilla))
    por_partido, por_usuario = generar(args.filas, args.semilla)

    ins_p = session.prepare(
        "INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, "
        "id_usuario, usuario_alias, equipo_apoyado, texto, minuto_partido, creado_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    ins_u = session.prepare(
        "INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, "
        "id_partido, texto, creado_en) VALUES (?, ?, ?, ?, ?, ?)")

    inicio = time.time()
    errores = 0
    for ps, filas in ((ins_p, por_partido), (ins_u, por_usuario)):
        resultados = execute_concurrent_with_args(session, ps, filas, concurrency=50,
                                                  raise_on_first_error=False)
        errores += sum(1 for ok, _ in resultados if not ok)
    duracion = time.time() - inicio

    # Validacion de la carga: contar lo que realmente quedo en cada tabla.
    conteo_p = session.execute("SELECT COUNT(*) FROM comentarios_por_partido", timeout=60).one()[0]
    conteo_u = session.execute("SELECT COUNT(*) FROM comentarios_por_usuario", timeout=60).one()[0]

    resumen = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "semilla": args.semilla,
        "filas_generadas": args.filas,
        "errores_insert": errores,
        "conteo_comentarios_por_partido": conteo_p,
        "conteo_comentarios_por_usuario": conteo_u,
        "filas_partido_caliente": sum(1 for f in por_partido if f[0] == comun.PARTIDO_CALIENTE),
        "duracion_s": round(duracion, 1),
    }
    print(json.dumps(resumen, indent=2))
    os.makedirs(comun.CARPETA_RESULTADOS, exist_ok=True)
    with open(os.path.join(comun.CARPETA_RESULTADOS, "preparacion.json"), "w") as f:
        json.dump(resumen, f, indent=2)
    cluster.shutdown()


if __name__ == "__main__":
    main()

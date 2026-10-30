"""
Hito 12 - CARGA Y MEDICION: muro de comentarios en vivo durante un pico post-gol.

Cada usuario virtual (un hilo) repite en loop:
  - 80% lectura del muro de un partido (ultimos 20 comentarios)
  - 20% publicacion de un comentario (2 inserts en Cassandra)
La mitad del trafico va al partido caliente P-001.

Los usuarios se reparten en varios procesos (--procesos) porque un solo
proceso Python queda limitado a un nucleo por el GIL y el generador pasaria
a ser el cuello de botella.

Modos:
  base        -> el muro se lee de Cassandra (12 consultas por lectura)
  optimizado  -> el muro se lee de Redis (LRANGE); la escritura ademas hace
                 LPUSHX + LTRIM en Redis

Uso:
    # prueba de capacidad (sin pausa entre operaciones)
    python scripts/ejecutar_carga.py --modo base --usuarios 50 --rampa 30 --duracion 120
    # carga fija: 50 usuarios x 10 ops/s = 500 ops/s ofrecidas
    python scripts/ejecutar_carga.py --modo base --usuarios 50 --tasa 10

Salida en docs/evidencia/resultados/:
  <modo>_<fecha>.json            metricas + configuracion + entorno
  <modo>_<fecha>_escrituras.csv  cada comentario intentado (para validar integridad)
"""

import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import signal
import statistics
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime, timezone

try:
    import resource
except ImportError:
    resource = None  # Windows nativo no dispone del modulo POSIX resource

from cassandra.util import uuid_from_time

import comun

INSERT_PARTIDO = (
    "INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, "
    "id_usuario, usuario_alias, equipo_apoyado, texto, minuto_partido, creado_en) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
INSERT_USUARIO = (
    "INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, "
    "id_partido, texto, creado_en) VALUES (?, ?, ?, ?, ?, ?)")


# ---------------------------------------------------------------- generador

def usuario_virtual(nro, args, session, r, ps, inicio, detener, ops, escrituras):
    # Rampa: los usuarios arrancan escalonados a lo largo de --rampa segundos.
    detener.wait(args.rampa * nro / args.usuarios)
    rnd = random.Random(args.semilla + nro)
    intervalo = 1 / args.tasa if args.tasa else 0
    proxima = time.time()
    while not detener.is_set():
        if intervalo:
            # Carga fija: cada usuario hace --tasa ops/s. Si se atrasa no
            # "recupera" operaciones, sigue desde ahora.
            proxima = max(proxima + intervalo, time.time())
            detener.wait(proxima - time.time())
            if detener.is_set():
                break
        partido = comun.elegir_partido(rnd)
        es_lectura = rnd.random() < args.lecturas
        t0 = time.perf_counter()
        error, hit = None, None
        try:
            if es_lectura:
                if args.modo == "base":
                    comun.leer_muro_cassandra(session, ps["leer"], partido)
                else:
                    _, hit = comun.leer_muro_redis(r, session, ps["leer"], partido)
            else:
                publicar(args.modo, session, r, ps, partido, rnd, escrituras)
        except Exception as e:
            error = type(e).__name__
        t1 = time.perf_counter()
        ops.append((time.time() - inicio, "lectura" if es_lectura else "escritura",
                    (t1 - t0) * 1000, error, hit))


def publicar(modo, session, r, ps, partido, rnd, escrituras):
    ahora = datetime.now(timezone.utc)
    usuario = comun.elegir_usuario(rnd)
    id_com = uuid_from_time(ahora)
    ventana, shard = comun.ventana_de(ahora), comun.shard_de(usuario)
    alias, texto = "hincha_" + usuario[2:], "Golazo"
    registro = [str(id_com), partido, ventana, shard, usuario, ahora.strftime("%Y%m"), "error"]
    escrituras.append(registro)

    f1 = session.execute_async(ps["ins_p"], (partido, ventana, shard, id_com, usuario,
                                             alias, "ARG", texto, 70, ahora))
    f2 = session.execute_async(ps["ins_u"], (usuario, ahora.strftime("%Y%m"), id_com,
                                             partido, texto, ahora))
    f1.result()
    f2.result()
    registro[-1] = "ok"  # aceptado = quedo en las dos tablas de Cassandra
    if modo == "optimizado":
        # LPUSHX solo agrega si el muro ya existe; si no existe lo arma la
        # proxima lectura desde Cassandra (evita muros incompletos).
        clave = "muro:" + partido
        pipe = r.pipeline()
        pipe.lpushx(clave, comun.a_json(id_com, alias, texto, ahora))
        pipe.ltrim(clave, 0, comun.TAM_MURO_REDIS - 1)
        pipe.execute()


def proceso(nro_proc, args, inicio, detener, cola):
    """Un proceso del generador: abre sus conexiones y corre sus usuarios en hilos."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # el Ctrl+C lo maneja el proceso principal
    cluster, session = comun.conectar_cassandra()
    r = comun.conectar_redis()
    ps = {"leer": comun.preparar_lectura(session),
          "ins_p": session.prepare(INSERT_PARTIDO),
          "ins_u": session.prepare(INSERT_USUARIO)}
    ops, escrituras = [], []
    mios = range(nro_proc, args.usuarios, args.procesos)  # usuarios de este proceso
    hilos = [threading.Thread(target=usuario_virtual,
                              args=(n, args, session, r, ps, inicio, detener, ops, escrituras))
             for n in mios]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    cluster.shutdown()
    cola.put((ops, escrituras))


# ---------------------------------------------------------------- medicion

def muestrear_recursos(muestras, inicio, detener):
    """docker stats cada 5 s de los contenedores del flujo."""
    while not detener.is_set():
        salida = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}",
             "fixture2030-cassandra", "fixture2030-redis"],
            capture_output=True, text=True).stdout
        for linea in salida.splitlines():
            d = json.loads(linea)
            muestras.append({"t": round(time.time() - inicio, 1), "contenedor": d["Name"],
                             "cpu": d["CPUPerc"], "mem": d["MemUsage"]})
        detener.wait(5)


def percentiles(valores):
    if len(valores) < 2:
        return {}
    q = statistics.quantiles(valores, n=100)
    return {"n": len(valores), "min": round(min(valores), 2),
            "promedio": round(statistics.mean(valores), 2), "p50": round(q[49], 2),
            "p95": round(q[94], 2), "p99": round(q[98], 2), "max": round(max(valores), 2)}


def entorno():
    cluster, session = comun.conectar_cassandra()
    r = comun.conectar_redis()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    sucio = subprocess.run(["git", "status", "--porcelain", "."],
                           capture_output=True, text=True).stdout.strip() != ""
    # Hash de los scripts: identifica la version exacta aunque no haya commit.
    h = hashlib.sha1()
    for nombre in sorted(os.listdir(os.path.dirname(__file__))):
        if nombre.endswith(".py"):
            h.update(open(os.path.join(os.path.dirname(__file__), nombre), "rb").read())
    datos = {
        "commit": commit + (" (con cambios sin commitear)" if sucio else ""),
        "sha1_scripts": h.hexdigest()[:12],
        "cassandra_version": session.execute("SELECT release_version FROM system.local").one()[0],
        "redis_version": r.info("server")["redis_version"],
        "redis_maxmemory_policy": r.config_get("maxmemory-policy")["maxmemory-policy"],
        "host": "%s %s, %s CPUs" % (platform.system(), platform.release(), os.cpu_count()),
        "python": platform.python_version(),
    }
    cluster.shutdown()
    return datos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["base", "optimizado"], required=True)
    ap.add_argument("--usuarios", type=int, default=50)
    ap.add_argument("--procesos", type=int, default=3)
    ap.add_argument("--rampa", type=int, default=30, help="segundos de ramp-up")
    ap.add_argument("--duracion", type=int, default=120, help="segundos de sostenimiento")
    ap.add_argument("--lecturas", type=float, default=0.8)
    ap.add_argument("--semilla", type=int, default=2030)
    ap.add_argument("--tasa", type=float, default=0,
                    help="ops/s por usuario (carga fija). 0 = sin pausa (prueba de capacidad)")
    args = ap.parse_args()

    if args.modo == "optimizado":
        # Arrancar siempre con Redis frio, igual que la linea base arranca sin muro.
        r = comun.conectar_redis()
        claves = list(r.scan_iter("muro:*"))
        if claves:
            r.delete(*claves)

    datos_entorno = entorno()
    detener, cola = mp.Event(), mp.Queue()
    inicio = time.time()
    muestras = []
    procesos = [mp.Process(target=proceso, args=(i, args, inicio, detener, cola))
                for i in range(args.procesos)]
    for p in procesos:
        p.start()
    hilo_recursos = threading.Thread(target=muestrear_recursos, args=(muestras, inicio, detener))
    hilo_recursos.start()

    total = args.rampa + args.duracion
    print("Modo %s: %d usuarios en %d procesos, rampa %ds, sostenimiento %ds, tasa %s" %
          (args.modo, args.usuarios, args.procesos, args.rampa, args.duracion,
           "%g ops/s por usuario" % args.tasa if args.tasa else "sin pausa"))
    corte = "tiempo cumplido"
    try:
        detener.wait(total)
    except KeyboardInterrupt:  # corte seguro con Ctrl+C: se guardan los resultados igual
        corte = "interrumpido por el usuario"
    detener.set()
    ops, escrituras = [], []
    for _ in procesos:
        o, e = cola.get()
        ops += o
        escrituras += e
    for p in procesos:
        p.join()
    hilo_recursos.join()
    pared = time.time() - inicio
    if resource is not None:
        hijos = resource.getrusage(resource.RUSAGE_CHILDREN)
        cliente_cpu_pct = round(100 * (hijos.ru_utime + hijos.ru_stime) / pared, 1)
    else:
        cliente_cpu_pct = None
    # Latencia vista DESDE Cassandra (coordinador), para separarla de la del cliente.
    # Son histogramas con decaimiento: reflejan sobre todo los ultimos minutos.
    proxy = subprocess.run(["docker", "exec", "fixture2030-cassandra", "nodetool", "proxyhistograms"],
                           capture_output=True, text=True).stdout.strip().splitlines()

    # Solo se miden las operaciones del periodo de sostenimiento (sin rampa).
    sostenido = [o for o in ops if o[0] >= args.rampa]
    ventana_s = max(0.001, min(pared, total) - args.rampa)
    por_segundo = Counter(int(o[0]) for o in ops)
    resultado = {
        "modo": args.modo,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "configuracion": vars(args),
        "entorno": datos_entorno,
        "corte": corte,
        "operaciones_totales": len(ops),
        "sostenimiento": {
            "segundos": round(ventana_s, 1),
            "operaciones": len(sostenido),
            "throughput_ops_s": round(len(sostenido) / ventana_s, 1),
            "errores": len([o for o in sostenido if o[3]]),
            "tasa_error_pct": round(100 * len([o for o in sostenido if o[3]]) / max(1, len(sostenido)), 2),
            "tipos_error": dict(Counter(o[3] for o in sostenido if o[3])),
        },
        "latencia_ms": {
            tipo: percentiles([o[2] for o in sostenido if o[1] == tipo and not o[3]])
            for tipo in ("lectura", "escritura")
        },
        "cache": {
            "hits": sum(1 for o in sostenido if o[4] is True),
            "misses": sum(1 for o in sostenido if o[4] is False),
        },
        "escrituras": {
            "intentadas": len(escrituras),
            "ok": sum(1 for e in escrituras if e[-1] == "ok"),
            "rechazadas": sum(1 for e in escrituras if e[-1] != "ok"),
        },
        # CPU de los procesos del generador, en % de UN nucleo. Si se acerca a
        # 100% x procesos, el cuello de botella puede ser el cliente.
        "cliente_cpu_pct": cliente_cpu_pct,
        "ops_por_segundo": [por_segundo[s] for s in range(int(pared))],
        "recursos_docker": muestras,
        "cassandra_proxyhistograms": proxy,
    }

    os.makedirs(comun.CARPETA_RESULTADOS, exist_ok=True)
    base = os.path.join(comun.CARPETA_RESULTADOS,
                        "%s_%s" % (args.modo, datetime.now().strftime("%Y%m%d-%H%M%S")))
    with open(base + ".json", "w") as f:
        json.dump(resultado, f, indent=2)
    with open(base + "_escrituras.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_comentario", "id_partido", "ventana", "shard", "id_usuario", "periodo", "estado"])
        w.writerows(escrituras)

    print(json.dumps({k: resultado[k] for k in
                      ("corte", "sostenimiento", "latencia_ms", "cache", "escrituras", "cliente_cpu_pct")},
                     indent=2))
    print("Resultados en", os.path.relpath(base) + ".json")


if __name__ == "__main__":
    main()

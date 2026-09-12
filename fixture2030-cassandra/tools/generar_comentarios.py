#!/usr/bin/env python3
"""
Hito 6 - Fixture 2030 - Generador de comentarios sinteticos (RF11).

Produce tres CSV listos para el comando COPY de cqlsh, uno por tabla:
    comentarios_por_partido.csv
    comentarios_por_usuario.csv
    comentarios_en_revision.csv

Solo usa la biblioteca estandar: no hace falta instalar nada, ni dentro ni
fuera del contenedor.

Distribucion generada (declarada para que el resultado sea interpretable):
  * Partidos: 64 (P-001..P-064). El 20% de los partidos concentra el 60% de
    los comentarios, para reproducir el escenario de "partido popular".
  * Usuarios: 200.000 alias sinteticos, elegidos con sesgo (los 5.000 mas
    activos generan ~30% del trafico).
  * Instantes: 120 ventanas de 1 minuto por partido (duracion de un encuentro
    con entretiempo), distribuidas con picos en los minutos de gol.
  * Estados: 92% publicado, 6% en_revision, 2% rechazado.
  * shard = crc32(id_usuario) % 4  -> misma formula que usan los scripts CQL.

Uso:
    python3 tools/generar_comentarios.py --filas 1000000 --salida data/
    python3 tools/generar_comentarios.py --filas 5000 --salida data/ --semilla 7
"""

import argparse
import csv
import os
import random
import time
import uuid
import zlib
from datetime import datetime, timedelta, timezone

SHARDS = 4
PARTIDOS = 64
USUARIOS = 200_000
USUARIOS_ACTIVOS = 5_000
VENTANAS_POR_PARTIDO = 120
EQUIPOS = ["ARG", "BRA", "URU", "ESP", "FRA", "ENG", "GER", "ITA",
           "MEX", "USA", "POR", "NED", "JPN", "KOR", "MAR", "SEN"]
IDIOMAS = ["es", "pt", "en"]
PESOS_IDIOMA = [0.55, 0.25, 0.20]
ESTADOS = ["publicado", "en_revision", "rechazado"]
PESOS_ESTADO = [0.92, 0.06, 0.02]
MOTIVOS = {"en_revision": "reporte_usuario", "rechazado": "filtro_automatico"}

FRASES = [
    "Que jugada, casi gol", "El arbitro cobro mal esa falta",
    "Golazo, imposible para el arquero", "Cambio necesario ya",
    "Atajada tremenda", "Penal clarisimo que no cobraron",
    "El VAR tarda demasiado", "Presionan alto, se viene el gol",
    "Partidazo, no se puede dejar de mirar", "Se descontrolo el partido",
    "Tiro libre peligroso", "Offside milimetrico",
    "Gran pase filtrado", "Otra vez fuera de posicion",
]

# Fecha base del torneo: primer partido del Fixture 2030.
INICIO = datetime(2030, 6, 15, 18, 0, 0, tzinfo=timezone.utc)


def shard_de(id_usuario: str) -> int:
    """Misma formula que documentan 02-tablas.cql y el README."""
    return zlib.crc32(id_usuario.encode()) % SHARDS


def timeuuid_v1(momento: datetime, contador: int) -> str:
    """
    timeuuid (UUID v1) derivado del instante del comentario.
    Se construye a mano para que el CSV sea reproducible con una semilla fija,
    en lugar de depender del reloj de la maquina que genera los datos.
    """
    # Intervalos de 100ns desde el 15/10/1582 (epoca UUID).
    cien_ns = int((momento.timestamp() + 12219292800) * 10_000_000) + contador
    time_low = cien_ns & 0xFFFFFFFF
    time_mid = (cien_ns >> 32) & 0xFFFF
    time_hi = ((cien_ns >> 48) & 0x0FFF) | 0x1000          # version 1
    clock_seq = (contador & 0x3FFF) | 0x8000               # variante RFC 4122
    nodo = 0x5F1C7,                                        # "fixture" en hexa
    return "%08x-%04x-%04x-%04x-%012x" % (
        time_low, time_mid, time_hi, clock_seq, nodo[0])


def elegir_partido(rnd: random.Random) -> int:
    """20% de los partidos concentra el 60% del trafico."""
    populares = max(1, PARTIDOS // 5)
    if rnd.random() < 0.60:
        return rnd.randrange(populares) + 1
    return rnd.randrange(populares, PARTIDOS) + 1


def elegir_usuario(rnd: random.Random) -> str:
    """Los 5.000 usuarios mas activos concentran ~30% de los comentarios."""
    if rnd.random() < 0.30:
        return "U-%06d" % rnd.randrange(USUARIOS_ACTIVOS)
    return "U-%06d" % rnd.randrange(USUARIOS)


def generar(filas: int, salida: str, semilla: int) -> None:
    rnd = random.Random(semilla)
    os.makedirs(salida, exist_ok=True)

    ruta_partido = os.path.join(salida, "comentarios_por_partido.csv")
    ruta_usuario = os.path.join(salida, "comentarios_por_usuario.csv")
    ruta_revision = os.path.join(salida, "comentarios_en_revision.csv")

    inicio = time.time()
    en_revision = 0

    with open(ruta_partido, "w", newline="", encoding="utf-8") as fp, \
         open(ruta_usuario, "w", newline="", encoding="utf-8") as fu, \
         open(ruta_revision, "w", newline="", encoding="utf-8") as fr:

        w_partido = csv.writer(fp)
        w_usuario = csv.writer(fu)
        w_revision = csv.writer(fr)

        # Encabezados: el COPY de cqlsh los usa con HEADER=TRUE.
        w_partido.writerow([
            "id_partido", "ventana", "shard", "id_comentario", "id_usuario",
            "usuario_alias", "equipo_apoyado", "texto", "idioma",
            "estado_moderacion", "minuto_partido", "creado_en"])
        w_usuario.writerow([
            "id_usuario", "periodo", "id_comentario", "id_partido", "texto",
            "estado_moderacion", "creado_en"])
        w_revision.writerow([
            "id_partido", "estado_moderacion", "id_comentario", "id_usuario",
            "texto", "motivo", "creado_en"])

        for n in range(filas):
            nro_partido = elegir_partido(rnd)
            id_partido = "P-%03d" % nro_partido
            id_usuario = elegir_usuario(rnd)

            # Minuto de juego con picos: los goles concentran comentarios.
            minuto = min(VENTANAS_POR_PARTIDO - 1,
                         int(abs(rnd.gauss(rnd.choice([23, 44, 67, 88]), 12))))
            # Cada partido arranca un dia distinto del calendario del torneo.
            arranque = INICIO + timedelta(days=nro_partido // 4,
                                          hours=3 * (nro_partido % 4))
            momento = arranque + timedelta(minutes=minuto,
                                           seconds=rnd.randrange(60))

            ventana = momento.strftime("%Y%m%d%H%M")
            periodo = momento.strftime("%Y%m")
            creado_en = momento.strftime("%Y-%m-%d %H:%M:%S%z")
            id_comentario = timeuuid_v1(momento, n)
            estado = rnd.choices(ESTADOS, PESOS_ESTADO)[0]
            idioma = rnd.choices(IDIOMAS, PESOS_IDIOMA)[0]
            texto = rnd.choice(FRASES)
            alias = "hincha_%s" % id_usuario[2:]
            equipo = rnd.choice(EQUIPOS)

            w_partido.writerow([
                id_partido, ventana, shard_de(id_usuario), id_comentario,
                id_usuario, alias, equipo, texto, idioma, estado,
                minuto, creado_en])
            w_usuario.writerow([
                id_usuario, periodo, id_comentario, id_partido, texto,
                estado, creado_en])
            if estado != "publicado":
                en_revision += 1
                w_revision.writerow([
                    id_partido, estado, id_comentario, id_usuario, texto,
                    MOTIVOS[estado], creado_en])

    duracion = time.time() - inicio
    print("Generacion terminada en %.1f s (%.0f filas/s)" % (
        duracion, filas / duracion if duracion else 0))
    print("  %-42s %d filas" % (ruta_partido, filas))
    print("  %-42s %d filas" % (ruta_usuario, filas))
    print("  %-42s %d filas" % (ruta_revision, en_revision))
    print("Semilla utilizada: %d (misma semilla = mismo dataset)" % semilla)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--filas", type=int, default=1_000_000,
                    help="cantidad de comentarios a generar (default 1.000.000)")
    ap.add_argument("--salida", default="data",
                    help="carpeta destino de los CSV (default ./data)")
    ap.add_argument("--semilla", type=int, default=2030,
                    help="semilla del generador, para reproducibilidad")
    args = ap.parse_args()
    generar(args.filas, args.salida, args.semilla)

"""
Hito 12 - VALIDACION DE INTEGRIDAD de una corrida de carga.

Uso:
    python scripts/validar_integridad.py docs/evidencia/resultados/base_20261029-120000.json

Controles (con el CSV de escrituras que deja ejecutar_carga.py):
  1. modo optimizado: el muro de Redis no tiene duplicados ni ids desconocidos,
     y cuantos de los ultimos comentarios reales le faltan (frescura).
     Va primero porque los muros vencen a los 60 s.
  2. generados vs aceptados vs rechazados, e id_comentario unicos
  3. cada comentario aceptado existe en las DOS tablas (por_partido y por_usuario)
  4. ningun rechazado quedo escrito a medias
  5. conteo por particion = cantidad esperada (detecta duplicados o perdidas)
"""

import csv
import gzip
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime

from cassandra.concurrent import execute_concurrent_with_args

import comun


def contar_ausentes(session, ps, params):
    """
    Cuenta cuantas filas NO existen. Las consultas que fallan (timeout de la
    propia validacion) se reintentan de a una: un error de lectura no es un dato perdido.
    """
    resultados = execute_concurrent_with_args(session, ps, params, concurrency=20,
                                              raise_on_first_error=False)
    ausentes, reintentos = 0, 0
    for p, (ok, res) in zip(params, resultados):
        if not ok:
            reintentos += 1
            res = session.execute(ps, p, timeout=10)
        if res.one() is None:
            ausentes += 1
    return ausentes, reintentos


def validar_redis(aceptadas, session, ps_p):
    r = comun.conectar_redis()
    aceptados_ids = {f["id_comentario"] for f in aceptadas}
    por_partido = defaultdict(list)
    for f in aceptadas:
        por_partido[f["id_partido"]].append(uuid.UUID(f["id_comentario"]))
    muros = {}
    for clave in r.scan_iter("muro:*"):
        elementos = [json.loads(x) for x in r.lrange(clave, 0, -1)]
        ids_muro = [e["id"] for e in elementos]
        # Un id que no es de esta corrida puede venir de una corrida anterior
        # (la reconstruccion lee los ultimos 3 minutos): se busca en Cassandra.
        inexistentes = 0
        for e in elementos:
            if e["id"] not in aceptados_ids:
                usuario = "U-" + e["alias"].split("_")[1]
                momento = datetime.fromisoformat(e["creado_en"])
                fila = session.execute(ps_p, (clave.split(":")[1], comun.ventana_de(momento),
                                              comun.shard_de(usuario), uuid.UUID(e["id"]))).one()
                inexistentes += fila is None
        ultimos = sorted(por_partido[clave.split(":")[1]], key=lambda u: u.time, reverse=True)
        ultimos = {str(u) for u in ultimos[:len(ids_muro)]}
        muros[clave] = {
            "elementos": len(ids_muro),
            "duplicados": len(ids_muro) - len(set(ids_muro)),
            "ids_de_corridas_previas": len(set(ids_muro) - aceptados_ids) - inexistentes,
            "ids_inexistentes_en_cassandra": inexistentes,
            # comentarios ya aceptados en Cassandra que el muro todavia no muestra
            "ultimos_reales_ausentes_en_muro": len(ultimos - set(ids_muro)),
        }
    return {
        "muros": len(muros),
        "muros_con_duplicados": sum(1 for m in muros.values() if m["duplicados"]),
        "ids_de_corridas_previas_total": sum(m["ids_de_corridas_previas"] for m in muros.values()),
        "ids_inexistentes_en_cassandra_total": sum(m["ids_inexistentes_en_cassandra"] for m in muros.values()),
        "ultimos_reales_ausentes_total": sum(m["ultimos_reales_ausentes_en_muro"] for m in muros.values()),
        "elementos_total": sum(m["elementos"] for m in muros.values()),
        "partido_caliente": muros.get("muro:" + comun.PARTIDO_CALIENTE),
    }


def main():
    ruta_json = sys.argv[1]
    resultado = json.load(open(ruta_json))
    ruta_csv = ruta_json.replace(".json", "_escrituras.csv")
    # La evidencia se guarda comprimida en el repo (.csv.gz)
    archivo = open(ruta_csv) if os.path.exists(ruta_csv) else gzip.open(ruta_csv + ".gz", "rt")
    filas = list(csv.DictReader(archivo))
    aceptadas = [f for f in filas if f["estado"] == "ok"]
    rechazadas = [f for f in filas if f["estado"] != "ok"]
    ids = Counter(f["id_comentario"] for f in filas)

    cluster, session = comun.conectar_cassandra()
    ps_p = session.prepare("SELECT id_comentario FROM comentarios_por_partido "
                           "WHERE id_partido=? AND ventana=? AND shard=? AND id_comentario=?")
    informe = {"corrida": ruta_json}
    if resultado["modo"] == "optimizado":
        informe["redis"] = validar_redis(aceptadas, session, ps_p)
    ps_u = session.prepare("SELECT id_comentario FROM comentarios_por_usuario "
                           "WHERE id_usuario=? AND periodo=? AND id_comentario=?")

    def params_p(fs):
        return [(f["id_partido"], f["ventana"], int(f["shard"]), uuid.UUID(f["id_comentario"])) for f in fs]

    def params_u(fs):
        return [(f["id_usuario"], f["periodo"], uuid.UUID(f["id_comentario"])) for f in fs]

    falta_p, reint_p = contar_ausentes(session, ps_p, params_p(aceptadas))
    falta_u, reint_u = contar_ausentes(session, ps_u, params_u(aceptadas))
    # Un rechazado "presente" es una escritura parcial.
    rech_p, _ = contar_ausentes(session, ps_p, params_p(rechazadas))
    rech_u, _ = contar_ausentes(session, ps_u, params_u(rechazadas))
    parciales = (len(rechazadas) - rech_p) + (len(rechazadas) - rech_u)

    # Conteo por particion: las ventanas son del minuto real de la corrida, asi
    # que esas particiones solo tienen filas de esta corrida.
    esperado = Counter((f["id_partido"], f["ventana"], int(f["shard"])) for f in aceptadas)
    ps_count = session.prepare("SELECT COUNT(*) FROM comentarios_por_partido "
                               "WHERE id_partido=? AND ventana=? AND shard=?")
    diferencias = {}
    for k in esperado:
        real = session.execute(ps_count, k, timeout=10).one()[0]
        if real != esperado[k]:
            diferencias["%s/%s/%s" % k] = {"esperado": esperado[k], "real": real}

    informe.update({
        "escrituras_generadas": len(filas),
        "aceptadas": len(aceptadas),
        "rechazadas": len(rechazadas),
        "ids_duplicados_en_cliente": sum(1 for n in ids.values() if n > 1),
        "aceptadas_faltantes_en_por_partido": falta_p,
        "aceptadas_faltantes_en_por_usuario": falta_u,
        "consultas_de_validacion_reintentadas": reint_p + reint_u,
        "rechazadas_escritas_parcialmente": parciales,
        "particiones_controladas": len(esperado),
        "filas_en_particiones_controladas": sum(esperado.values()),
        "particiones_con_diferencias": diferencias,
    })
    ok = (informe["ids_duplicados_en_cliente"] == 0 and falta_p == 0 and falta_u == 0
          and parciales == 0 and not diferencias
          and informe.get("redis", {}).get("muros_con_duplicados", 0) == 0
          and informe.get("redis", {}).get("ids_inexistentes_en_cassandra_total", 0) == 0)
    informe["resultado"] = "OK" if ok else "CON PROBLEMAS"
    print(json.dumps(informe, indent=2))
    with open(ruta_json.replace(".json", "_integridad.json"), "w") as f:
        json.dump(informe, f, indent=2)
    cluster.shutdown()


if __name__ == "__main__":
    main()

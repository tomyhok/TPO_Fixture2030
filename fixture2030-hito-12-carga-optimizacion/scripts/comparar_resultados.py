"""
Hito 12 - COMPARACION antes/despues. Genera una tabla Markdown.

Uso:
    python scripts/comparar_resultados.py <base.json> <optimizado.json>
"""

import json
import os
import sys

import comun


def variacion(a, b):
    if a is None or b is None or not a:
        return "-"
    return "%+.1f%%" % (100 * (b - a) / a)


def main():
    base, opt = (json.load(open(p)) for p in sys.argv[1:3])
    filas = [("Throughput (ops/s)", base["sostenimiento"]["throughput_ops_s"],
              opt["sostenimiento"]["throughput_ops_s"]),
             ("Operaciones en sostenimiento", base["sostenimiento"]["operaciones"],
              opt["sostenimiento"]["operaciones"]),
             ("Errores", base["sostenimiento"]["errores"], opt["sostenimiento"]["errores"])]
    for tipo in ("lectura", "escritura"):
        for p in ("p50", "p95", "p99", "max"):
            filas.append(("Latencia %s %s (ms)" % (tipo, p),
                          base["latencia_ms"][tipo].get(p), opt["latencia_ms"][tipo].get(p)))
    filas.append(("CPU del generador (%)", base["cliente_cpu_pct"], opt["cliente_cpu_pct"]))

    lineas = ["| Metrica | Linea base | Optimizado | Variacion |", "|---|---:|---:|---:|"]
    lineas += ["| %s | %s | %s | %s |" % (n, a, b, variacion(a, b)) for n, a, b in filas]
    lineas += ["", "- Linea base: `%s` (%s, commit %s)" % (sys.argv[1], base["fecha"], base["entorno"]["commit"]),
               "- Optimizado: `%s` (%s, commit %s)" % (sys.argv[2], opt["fecha"], opt["entorno"]["commit"]),
               "- Cache optimizado: %d hits / %d misses" % (opt["cache"]["hits"], opt["cache"]["misses"])]
    texto = "\n".join(lineas)
    print(texto)
    with open(os.path.join(comun.CARPETA_RESULTADOS, "..", "comparacion.md"), "w") as f:
        f.write("# Comparacion linea base vs optimizado\n\n" + texto + "\n")


if __name__ == "__main__":
    main()

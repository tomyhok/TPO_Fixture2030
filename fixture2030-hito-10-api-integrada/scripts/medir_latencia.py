"""Medición básica de latencia de la API (RNF18).

Método: requests HTTP secuenciales (un cliente, sin concurrencia) contra la API
ya levantada, con 10 requests de calentamiento descartadas por endpoint. Se
informan percentiles de la latencia observada por el cliente (incluye la red
local, la API y la fuente). Las cifras solo valen para el entorno descripto en
la salida: una notebook con todas las bases en Docker Desktop.

Uso (con la API levantada):
    .venv/Scripts/python scripts/medir_latencia.py --n 200 --salida docs/evidencia/12_latencia.md
"""

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime

import httpx

ESCENARIOS = [
    ("MongoDB", "GET /equipos/{codigo}", "/equipos/ARG"),
    ("MongoDB", "GET /equipos?size=10", "/equipos?size=10&page=2"),
    ("Neo4j", "GET /partidos/{c}/eventos", "/partidos/P-001/eventos"),
    ("Redis+Neo4j", "GET /partidos/{c} (cache HIT)", "/partidos/P-001"),
    ("Cassandra", "GET /partidos/{c}/comentarios", "/partidos/P-001/comentarios?ventana=203006152015&limit=20"),
    ("Redis", "GET /sesiones/{id} (404)", "/sesiones/S-9999"),
    ("InfluxDB", "GET /estadisticas 30 min @1m", "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:30:00Z&resolucion=1m"),
    ("InfluxDB", "GET /estadisticas 3 h @10s", "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T23:00:00Z&resolucion=10s"),
    ("IRIS", "GET /partidos-oficiales/{c}", "/partidos-oficiales/P-001"),
    ("Validación", "GET /equipos/arg (400)", "/equipos/arg"),
]


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p
    i = int(k)
    return ordenados[i] + (ordenados[min(i + 1, len(ordenados) - 1)] - ordenados[i]) * (k - i)


def version_docker() -> str:
    try:
        return subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--salida")
    args = parser.parse_args()

    filas = []
    with httpx.Client(base_url=args.base, timeout=30) as cliente:
        for fuente, nombre, ruta in ESCENARIOS:
            for _ in range(10):
                cliente.get(ruta)
            tiempos, estados = [], {}
            for _ in range(args.n):
                inicio = time.perf_counter()
                r = cliente.get(ruta)
                tiempos.append((time.perf_counter() - inicio) * 1000)
                estados[r.status_code] = estados.get(r.status_code, 0) + 1
            filas.append((fuente, nombre, estados, tiempos))

    lineas = [
        "# Medición básica de latencia (RNF18)",
        "",
        f"- **Fecha (UTC):** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Método:** {args.n} requests HTTP secuenciales por escenario (1 cliente, sin concurrencia), "
        "10 de calentamiento descartadas. Latencia medida en el cliente (`time.perf_counter`).",
        f"- **Entorno:** {platform.system()} {platform.release()}, {os.cpu_count()} CPU lógicas, "
        f"Python {platform.python_version()}, Docker Engine {version_docker()} (Docker Desktop). "
        "API con uvicorn (1 worker) en la notebook; las seis bases en contenedores del `docker-compose.yml` raíz.",
        "- **Volumen de datos:** 64 selecciones y 1.472 jugadores (MongoDB); grafo del Hito 5; muestra de "
        "35 comentarios del Hito 6 más los creados por las pruebas; 28.800 puntos de P-001/P-002 en InfluxDB "
        "(además de los del Hito 8); 3 actas en IRIS.",
        "- **Configuración:** timeouts de conexión 2 s y de operación 5 s; nivel de log INFO.",
        "",
        "| Fuente | Escenario | Respuestas | p50 (ms) | p95 (ms) | p99 (ms) | máx (ms) |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for fuente, nombre, estados, t in filas:
        resp = ", ".join(f"{c}×{n}" for c, n in sorted(estados.items()))
        lineas.append(
            f"| {fuente} | {nombre} | {resp} | {statistics.median(t):.1f} | {percentil(t, 0.95):.1f} | "
            f"{percentil(t, 0.99):.1f} | {max(t):.1f} |"
        )
    lineas += [
        "",
        "**Limitaciones.** Un solo cliente secuencial no mide throughput ni comportamiento bajo carga "
        "concurrente; todas las bases comparten CPU y memoria de la notebook con la API; cada base es un "
        "nodo único sin réplicas; los volúmenes son de laboratorio. Las cifras sirven para comparar "
        "escenarios entre sí en este entorno, no para dimensionar producción.",
    ]
    texto = "\n".join(lineas) + "\n"
    print(texto)
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())

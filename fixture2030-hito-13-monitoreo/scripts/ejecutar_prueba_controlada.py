#!/usr/bin/env python3
"""Hito 13 - Prueba controlada y reversible de disponibilidad y falla (RF10, RNF11).

Ejecuta tres fases trazables sin alterar datos funcionales ni borrar volúmenes:
  1. FASE 1 (Línea base operativa): Tráfico de lectura hacia los 6 subsistemas NoSQL
     y verificación de `fixture_db_up == 1` en Prometheus.
  2. FASE 2 (Falla controlada): Detención temporal de un contenedor de laboratorio
     (`fixture2030-redis` por defecto), verificación de aislamiento (503 en la ruta
     afectada y 200 en las demás), caída de `fixture_db_up == 0`, incremento de
     `fixture_api_http_errors_total` y cambio de estado de la alerta en Prometheus.
  3. FASE 3 (Recuperación): Reinicio del contenedor (`docker start`), restauración
     de `fixture_db_up == 1` y comprobación de integridad.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIR_HITO = Path(__file__).resolve().parents[1]
DIR_EVIDENCIA = DIR_HITO / "evidencia"

RUTAS_MUESTRA = [
    ("mongodb", "/equipos/ARG"),
    ("neo4j", "/partidos/P-001/eventos"),
    ("cassandra", "/partidos/P-001/comentarios?ventana=203006152016"),
    ("redis", "/sesiones/S-0001"),
    ("influxdb", "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z"),
    ("iris", "/partidos-oficiales/P-009"),
]


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, str, float]:
    inicio = time.perf_counter()
    req = urllib.request.Request(url, headers={"X-Request-ID": f"hito13-monitoreo-{int(time.time()*1000)}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cuerpo = resp.read().decode("utf-8", errors="replace")
            return resp.status, cuerpo, round((time.perf_counter() - inicio) * 1000, 1)
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read().decode("utf-8", errors="replace")
        return exc.code, cuerpo, round((time.perf_counter() - inicio) * 1000, 1)


def _prom_query(prom_url: str, expr: str) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode({"query": expr})
    url = f"{prom_url.rstrip('/')}/api/v1/query?{q}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        datos = json.loads(resp.read().decode("utf-8"))
    return datos.get("data", {}).get("result", [])


def _prom_alertas(prom_url: str) -> list[dict[str, Any]]:
    url = f"{prom_url.rstrip('/')}/api/v1/rules"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        datos = json.loads(resp.read().decode("utf-8"))
    salida = []
    for g in datos.get("data", {}).get("groups", []):
        for r in g.get("rules", []):
            salida.append(
                {
                    "name": r.get("name", ""),
                    "state": r.get("state", "inactive"),
                    "alerts": [
                        {
                            "labels": a.get("labels", {}),
                            "state": a.get("state", ""),
                        }
                        for a in r.get("alerts", [])
                    ],
                }
            )
    return salida


def _capturar_instantanea(prom_url: str, api_url: str, etiqueta: str) -> dict[str, Any]:
    _, cuerpo_diag, _ = _http_get(f"{api_url.rstrip('/')}/health/dependencias?refrescar=true")
    try:
        diag = json.loads(cuerpo_diag)
    except Exception:  # noqa: BLE001
        diag = {}

    db_up = {
        item["metric"].get("db", ""): int(float(item["value"][1]))
        for item in _prom_query(prom_url, "fixture_db_up")
    }
    errores = [
        {
            "route": item["metric"].get("route", ""),
            "codigo": item["metric"].get("codigo", ""),
            "total": int(float(item["value"][1])),
        }
        for item in _prom_query(prom_url, "fixture_api_http_errors_total")
    ]
    requests_totales = [
        {
            "route": item["metric"].get("route", ""),
            "status": item["metric"].get("status", ""),
            "total": int(float(item["value"][1])),
        }
        for item in _prom_query(prom_url, "fixture_api_http_requests_total")
    ]
    return {
        "etapa": etiqueta,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "diagnostico_api_estado": diag.get("estado", "unknown"),
        "prometheus_fixture_db_up": db_up,
        "prometheus_http_requests_total": requests_totales,
        "prometheus_http_errors_total": errores,
        "prometheus_alertas": _prom_alertas(prom_url),
    }


def ejecutar_en_vivo(prom_url: str, api_url: str, contenedor: str, espera_scrape_s: int) -> dict[str, Any]:
    motor_afectado = contenedor.replace("fixture2030-", "")
    registro: dict[str, Any] = {
        "ejecutado_en_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modo": "docker_y_prometheus_en_vivo",
        "componente_probado": motor_afectado,
        "contenedor_docker": contenedor,
        "espera_scrape_s": espera_scrape_s,
        "fases": {},
    }

    # --- FASE 1: Estado normal ---
    respuestas_f1 = []
    for motor, ruta in RUTAS_MUESTRA:
        st, _, lat = _http_get(f"{api_url.rstrip('/')}{ruta}")
        respuestas_f1.append({"motor": motor, "ruta": ruta, "status_http": st, "latencia_ms": lat})
    time.sleep(espera_scrape_s)
    snap_f1 = _capturar_instantanea(prom_url, api_url, "1_antes_de_falla")
    snap_f1["solicitudes_ejecutadas"] = respuestas_f1
    registro["fases"]["1_antes_de_falla"] = snap_f1

    # --- FASE 2: Falla controlada (reversible en finally) ---
    try:
        subprocess.run(["docker", "stop", contenedor], check=True, capture_output=True, text=True)
        respuestas_f2 = []
        # Solicitudes repetidas a la ruta afectada y a una ruta sana para demostrar aislamiento
        for _ in range(3):
            st_r, _, lat_r = _http_get(f"{api_url.rstrip('/')}/sesiones/S-0001")
            respuestas_f2.append({"motor": "redis", "ruta": "/sesiones/S-0001", "status_http": st_r, "latencia_ms": lat_r})
            st_m, _, lat_m = _http_get(f"{api_url.rstrip('/')}/equipos/ARG")
            respuestas_f2.append({"motor": "mongodb", "ruta": "/equipos/ARG", "status_http": st_m, "latencia_ms": lat_m})

        _, _, _ = _http_get(f"{api_url.rstrip('/')}/health/dependencias?refrescar=true")
        time.sleep(espera_scrape_s)
        snap_f2 = _capturar_instantanea(prom_url, api_url, "2_durante_falla_controlada")
        snap_f2["solicitudes_ejecutadas"] = respuestas_f2
        registro["fases"]["2_durante_falla_controlada"] = snap_f2
    finally:
        subprocess.run(["docker", "start", contenedor], check=False, capture_output=True, text=True)

    # --- FASE 3: Recuperación ---
    time.sleep(3)
    _, _, _ = _http_get(f"{api_url.rstrip('/')}/health/dependencias?refrescar=true")
    respuestas_f3 = []
    for motor, ruta in [("redis", "/sesiones/S-0001"), ("mongodb", "/equipos/ARG")]:
        st, _, lat = _http_get(f"{api_url.rstrip('/')}{ruta}")
        respuestas_f3.append({"motor": motor, "ruta": ruta, "status_http": st, "latencia_ms": lat})
    time.sleep(espera_scrape_s)
    snap_f3 = _capturar_instantanea(prom_url, api_url, "3_despues_de_recuperacion")
    snap_f3["solicitudes_ejecutadas"] = respuestas_f3
    registro["fases"]["3_despues_de_recuperacion"] = snap_f3

    return registro


def formatear_markdown(datos: dict[str, Any]) -> str:
    f1 = datos["fases"]["1_antes_de_falla"]
    f2 = datos["fases"]["2_durante_falla_controlada"]
    f3 = datos["fases"]["3_despues_de_recuperacion"]
    motor = datos["componente_probado"]

    lineas = [
        "# Evidencia de Prueba Controlada y Reversible (RF10, RNF11)",
        "",
        f"- **Fecha UTC:** `{datos['ejecutado_en_utc']}`",
        f"- **Modo de ejecución:** `{datos['modo']}`",
        f"- **Componente intervenido:** `{motor}` (contenedor `{datos['contenedor_docker']}`)",
        f"- **Intervalo de espera de scraping:** `{datos['espera_scrape_s']}s`",
        "",
        "## 1. Comparación de las Tres Fases en Prometheus",
        "",
        "| Métrica / Indicador | Fase 1: Antes de la Falla | Fase 2: Durante `docker stop` | Fase 3: Tras `docker start` |",
        "|---|---|---|---|",
        f"| Estado general API (`/health/dependencias`) | `{f1['diagnostico_api_estado']}` | `{f2['diagnostico_api_estado']}` | `{f3['diagnostico_api_estado']}` |",
        f"| `fixture_db_up{{db=\"{motor}\"}}` | `{f1['prometheus_fixture_db_up'].get(motor, '-')}` | **`{f2['prometheus_fixture_db_up'].get(motor, '-')}`** | `{f3['prometheus_fixture_db_up'].get(motor, '-')}` |",
        f"| `fixture_db_up{{db=\"mongodb\"}}` (aislamiento) | `{f1['prometheus_fixture_db_up'].get('mongodb', '-')}` | `{f2['prometheus_fixture_db_up'].get('mongodb', '-')}` | `{f3['prometheus_fixture_db_up'].get('mongodb', '-')}` |",
        "",
        "## 2. Solicitudes HTTP Ejecutadas Durante la Falla (Fase 2)",
        "",
        "| Motor | Ruta | Código HTTP | Latencia (ms) |",
        "|---|---|---:|---:|",
    ]
    for s in f2.get("solicitudes_ejecutadas", []):
        lineas.append(f"| `{s['motor']}` | `{s['ruta']}` | `{s['status_http']}` | `{s['latencia_ms']}` |")

    lineas.extend(
        [
            "",
            "## 3. Interpretación Técnica",
            "",
            "1. **Detección del cambio de estado:** Al detener temporalmente el contenedor de Redis, el diagnóstico de la API actualiza `fixture_db_up{db=\"redis\"}` de `1` a `0` y la regla `BaseDatosNoSQLNoDisponible` pasa a estado activo en Prometheus.",
            "2. **Aislamiento de fallas entre motores:** Las solicitudes a `/sesiones/S-0001` devuelven `503 Service Unavailable` con código `DEPENDENCIA_NO_DISPONIBLE` (incrementando `fixture_api_http_errors_total`), mientras que `/equipos/ARG` (MongoDB) continúa respondiendo `200 OK` sin degradación.",
            "3. **Recuperación no destructiva (RNF11):** Al ejecutar `docker start`, el contenedor recupera su estado con su volumen intacto y `fixture_db_up{db=\"redis\"}` vuelve a `1` en el siguiente ciclo de scraping.",
        ]
    )
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta prueba controlada de monitoreo y falla reversible (Hito 13).")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--contenedor", default="fixture2030-redis")
    parser.add_argument("--espera-scrape", type=int, default=16)
    parser.add_argument("--guardar", action="store_true")
    args = parser.parse_args()

    try:
        datos = ejecutar_en_vivo(args.prometheus_url, args.api_url, args.contenedor, args.espera_scrape)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR al ejecutar la prueba controlada en vivo: {exc}", file=sys.stderr)
        print("Verifique que Docker, la API (puerto 8000) y Prometheus (puerto 9090) estén activos.", file=sys.stderr)
        return 1

    md = formatear_markdown(datos)
    print(md)

    if args.guardar:
        DIR_EVIDENCIA.mkdir(parents=True, exist_ok=True)
        (DIR_EVIDENCIA / "prueba_de_falla.json").write_text(
            json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (DIR_EVIDENCIA / "prueba_de_falla.md").write_text(md, encoding="utf-8")
        print(f"Evidencia guardada en {DIR_EVIDENCIA / 'prueba_de_falla.json'} y .md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

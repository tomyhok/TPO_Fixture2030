#!/usr/bin/env python3
"""Hito 13 - Verificador reproducible de targets, reglas y métricas en Prometheus.

Consulta:
  * GET http://localhost:9090/api/v1/targets
  * GET http://localhost:9090/api/v1/rules
  * GET http://localhost:9090/api/v1/query?query=up
  * GET http://localhost:9090/api/v1/query?query=fixture_db_up
  * GET http://localhost:8000/metrics

Guarda evidencia limpia (sin secretos) en `evidencia/prometheus_targets.json`
y `evidencia/prometheus_targets.txt`.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIR_HITO = Path(__file__).resolve().parents[1]
DIR_EVIDENCIA = DIR_HITO / "evidencia"


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_text(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def verificar_en_vivo(prom_url: str, api_url: str) -> dict[str, Any]:
    ahora = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    resultado: dict[str, Any] = {
        "verificado_en_utc": ahora,
        "modo": "prometheus_en_vivo",
        "prometheus_url": prom_url,
        "api_url": api_url,
        "targets": [],
        "reglas": [],
        "consulta_up": [],
        "consulta_fixture_db_up": [],
        "muestra_endpoint_metrics": [],
    }

    # 1. Targets activos en Prometheus
    datos_targets = _get_json(f"{prom_url.rstrip('/')}/api/v1/targets")
    activos = datos_targets.get("data", {}).get("activeTargets", [])
    for t in activos:
        labels = t.get("labels", {})
        resultado["targets"].append(
            {
                "job": labels.get("job", ""),
                "instance": labels.get("instance", ""),
                "capa": labels.get("capa", ""),
                "componente": labels.get("componente", ""),
                "scrapeUrl": t.get("scrapeUrl", ""),
                "health": t.get("health", "unknown"),
                "lastScrape": t.get("lastScrape", ""),
                "lastScrapeDuration_s": round(float(t.get("lastScrapeDuration", 0.0)), 4),
                "lastError": t.get("lastError", ""),
            }
        )

    # 2. Reglas de alerta cargadas
    datos_reglas = _get_json(f"{prom_url.rstrip('/')}/api/v1/rules")
    for grupo in datos_reglas.get("data", {}).get("groups", []):
        for r in grupo.get("rules", []):
            resultado["reglas"].append(
                {
                    "grupo": grupo.get("name", ""),
                    "nombre": r.get("name", ""),
                    "query": r.get("query", ""),
                    "duration_s": r.get("duration", 0),
                    "health": r.get("health", ""),
                    "state": r.get("state", "inactive"),
                    "severity": r.get("labels", {}).get("severity", ""),
                }
            )

    # 3. Consulta PromQL `up`
    q_up = _get_json(f"{prom_url.rstrip('/')}/api/v1/query?query=up")
    for item in q_up.get("data", {}).get("result", []):
        m = item.get("metric", {})
        val = item.get("value", [0, "0"])
        resultado["consulta_up"].append(
            {"job": m.get("job", ""), "instance": m.get("instance", ""), "valor": int(float(val[1]))}
        )

    # 4. Consulta PromQL `fixture_db_up`
    q_db = _get_json(f"{prom_url.rstrip('/')}/api/v1/query?query=fixture_db_up")
    for item in q_db.get("data", {}).get("result", []):
        m = item.get("metric", {})
        val = item.get("value", [0, "0"])
        resultado["consulta_fixture_db_up"].append(
            {"db": m.get("db", ""), "valor": int(float(val[1]))}
        )

    # 5. Muestra directa de /metrics en la API integrada
    try:
        texto_m = _get_text(f"{api_url.rstrip('/')}/metrics")
        lineas = [
            ln
            for ln in texto_m.splitlines()
            if ln and not ln.startswith("#") and ("fixture_api_up" in ln or "fixture_db_up" in ln or "fixture_api_http_requests_total" in ln)
        ]
        resultado["muestra_endpoint_metrics"] = lineas[:20]
    except Exception as exc:  # noqa: BLE001
        resultado["muestra_endpoint_metrics"] = [f"No se pudo leer {api_url}/metrics directamente: {type(exc).__name__}"]

    return resultado


def formatear_resumen(datos: dict[str, Any]) -> str:
    lineas = [
        "======================================================================",
        "HITO 13 — VERIFICACIÓN DE TARGETS Y REGLAS EN PROMETHEUS",
        "======================================================================",
        f"Fecha UTC:      {datos['verificado_en_utc']}",
        f"Modo:           {datos['modo']}",
        f"Prometheus URL: {datos['prometheus_url']}",
        f"API URL:        {datos['api_url']}",
        "",
        "1. TARGETS CONFIGURADOS (/api/v1/targets):",
        f"  {'JOB':<16} {'INSTANCE':<28} {'CAPA':<16} {'HEALTH':<8} {'DURACION(s)':<12} {'ERROR'}",
        "  " + "-" * 92,
    ]
    for t in datos.get("targets", []):
        lineas.append(
            f"  {t['job']:<16} {t['instance']:<28} {t.get('capa','-'):<16} "
            f"{t['health'].upper():<8} {t['lastScrapeDuration_s']:<12.4f} {t['lastError'] or '-'}"
        )

    lineas.extend(
        [
            "",
            "2. ESTADO DE BASES DE DATOS NoSQL (PromQL: fixture_db_up):",
        ]
    )
    if datos.get("consulta_fixture_db_up"):
        for db in sorted(datos["consulta_fixture_db_up"], key=lambda x: x["db"]):
            estado_txt = "UP (1)" if db["valor"] == 1 else "DOWN (0)"
            lineas.append(f"  - {db['db']:<12}: {estado_txt}")
    else:
        lineas.append("  (Sin series fixture_db_up recolectadas aún)")

    lineas.extend(
        [
            "",
            "3. REGLAS DE ALERTA CARGADAS (/api/v1/rules):",
        ]
    )
    for r in datos.get("reglas", []):
        lineas.append(
            f"  - {r['nombre']:<30} [{r['severity'].upper():<8}] state={r['state']:<8} health={r['health']} (for={r['duration_s']}s)"
        )

    lineas.extend(
        [
            "",
            "4. MUESTRA DIRECTA DE /metrics EN LA API INTEGRADA:",
        ]
    )
    for ln in datos.get("muestra_endpoint_metrics", []):
        lineas.append(f"  {ln}")

    lineas.append("======================================================================")
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica targets y reglas en Prometheus (Hito 13).")
    parser.add_argument("--prometheus-url", default="http://localhost:9090", help="URL base de Prometheus")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL base de la API integrada")
    parser.add_argument("--guardar", action="store_true", help="Guarda la salida en evidencia/prometheus_targets.*")
    args = parser.parse_args()

    try:
        datos = verificar_en_vivo(args.prometheus_url, args.api_url)
    except urllib.error.URLError as exc:
        print(f"ERROR: No se pudo conectar con Prometheus en {args.prometheus_url}: {exc}", file=sys.stderr)
        print("Asegúrese de ejecutar primero: bash scripts/iniciar_monitoreo.sh", file=sys.stderr)
        return 1

    resumen = formatear_resumen(datos)
    print(resumen)

    if args.guardar:
        DIR_EVIDENCIA.mkdir(parents=True, exist_ok=True)
        (DIR_EVIDENCIA / "prometheus_targets.json").write_text(
            json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (DIR_EVIDENCIA / "prometheus_targets.txt").write_text(resumen, encoding="utf-8")
        print(f"Evidencia guardada en {DIR_EVIDENCIA / 'prometheus_targets.json'} y .txt")

    todos_up = bool(datos["targets"]) and all(t["health"] == "up" for t in datos["targets"])
    return 0 if todos_up else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Hito 13 - Exporta los datos de TODOS los paneles del dashboard desde Prometheus.

Lee las consultas PromQL de grafana/dashboards/fixture2030_war_room.json y ejecuta cada una
con /api/v1/query_range sobre la ventana indicada. A diferencia de "Inspect -> Data" de Grafana,
incluye todas las series de cada panel, con valores numéricos sin formato y timestamps en UTC.

Salida (en evidencia/dashboards/ por defecto):
  - datos_paneles_<desde>.json : metadatos (ventana, paso, consultas) + series completas
  - datos_paneles_<desde>.csv  : formato largo, una fila por (panel, serie, timestamp)

Uso:
  python scripts/exportar_datos_dashboard.py --desde 2026-11-23T20:38:00Z --hasta 2026-11-23T20:52:00Z
"""
from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DIR_HITO = Path(__file__).resolve().parent.parent
DASHBOARD = DIR_HITO / "grafana" / "dashboards" / "fixture2030_war_room.json"


def _query_range(prom: str, expr: str, desde: str, hasta: str, paso: str) -> list[dict]:
    datos = urllib.parse.urlencode({"query": expr, "start": desde, "end": hasta, "step": paso}).encode()
    req = urllib.request.Request(f"{prom.rstrip('/')}/api/v1/query_range", data=datos,
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        cuerpo = json.load(resp)
    if cuerpo.get("status") != "success":
        raise RuntimeError(f"Prometheus devolvió error para {expr}: {cuerpo}")
    return cuerpo["data"]["result"]


def _ts(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prometheus-url", default="http://localhost:9090")
    ap.add_argument("--desde", required=True, help="Inicio en UTC, RFC3339 (ej. 2026-11-23T20:38:00Z)")
    ap.add_argument("--hasta", required=True, help="Fin en UTC, RFC3339")
    ap.add_argument("--paso", default="15s", help="Resolución (por defecto 15s = scrape_interval)")
    ap.add_argument("--salida", default=str(DIR_HITO / "evidencia" / "dashboards"))
    args = ap.parse_args()

    tablero = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    paneles = []
    filas_csv = []
    for panel in tablero["panels"]:
        if panel.get("type") == "row":
            continue
        unidad = panel.get("fieldConfig", {}).get("defaults", {}).get("unit", "")
        consultas = []
        for tgt in panel.get("targets", []):
            resultado = _query_range(args.prometheus_url, tgt["expr"], args.desde, args.hasta, args.paso)
            series = []
            for serie in resultado:
                etiquetas = serie["metric"]
                valores = [[_ts(t), float(v)] for t, v in serie["values"]]
                series.append({"etiquetas": etiquetas, "valores": valores})
                nombre = ",".join(f"{k}={v}" for k, v in sorted(etiquetas.items())) or "(sin etiquetas)"
                for ts, val in valores:
                    filas_csv.append([panel["title"], tgt["refId"], nombre, ts, val, unidad])
            consultas.append({"refId": tgt["refId"], "expr": tgt["expr"], "series": series})
        paneles.append({"id": panel["id"], "titulo": panel["title"], "unidad": unidad, "consultas": consultas})

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    sufijo = args.desde.replace(":", "").replace("-", "")
    meta = {
        "generado_en_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": f"{args.prometheus_url}/api/v1/query_range",
        "dashboard": str(DASHBOARD.relative_to(DIR_HITO)).replace("\\", "/"),
        "dashboard_uid": tablero.get("uid"),
        "ventana_utc": {"desde": args.desde, "hasta": args.hasta, "paso": args.paso},
        "paneles": paneles,
    }
    ruta_json = salida / f"datos_paneles_{sufijo}.json"
    ruta_csv = salida / f"datos_paneles_{sufijo}.csv"
    ruta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    with ruta_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["panel", "consulta", "serie", "timestamp_utc", "valor", "unidad"])
        w.writerows(filas_csv)

    total_series = sum(len(c["series"]) for p in paneles for c in p["consultas"])
    print(f"Paneles: {len(paneles)} | series: {total_series} | filas CSV: {len(filas_csv)}")
    print(f"Guardado: {ruta_json}\n          {ruta_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

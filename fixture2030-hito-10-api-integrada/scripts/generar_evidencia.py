"""Captura HTTP de las seis lecturas. No modifica datos ni detiene motores."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.settings import obtener_settings

CASOS = [
    ("mongodb", "/equipos/ARG"),
    ("neo4j", "/partidos/P-001/eventos?limit=5"),
    ("cassandra", "/partidos/P-001/comentarios?ventana=203006152015&limit=5"),
    ("redis", "/sesiones/S-0001"),
    ("influxdb", "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z"),
    ("iris", "/partidos-oficiales/P-009"),
    ("salud", "/health/dependencias"),
]


def main():
    settings = obtener_settings()
    base = f"http://127.0.0.1:{settings.api_port}"
    fecha = datetime.now(timezone.utc)
    out = ROOT / "docs/evidencia" / fecha.strftime("http_%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    resultados = []
    with httpx.Client(base_url=base, timeout=15) as cliente:
        for n, (fuente, ruta) in enumerate(CASOS):
            rid = f"h10-{fecha:%Y%m%dT%H%M%S}-{n}"
            try:
                r = cliente.get(ruta, headers={"X-Request-ID": rid})
                resultados.append({"fuente": fuente, "ruta": ruta, "status": r.status_code,
                                   "request_id": r.headers.get("x-request-id"), "cuerpo": r.json()})
                print(f"{fuente}: HTTP {r.status_code}")
            except (httpx.HTTPError, ValueError):
                resultados.append({"fuente": fuente, "ruta": ruta, "error": "sin respuesta JSON válida"})
                print(f"{fuente}: sin respuesta JSON válida")
    (out / "resultados.json").write_text(json.dumps({"fecha_utc": fecha.isoformat(),
        "transporte": "HTTP contra servidor iniciado", "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    correcto = all(r.get("status") == 200 or
                    (r["fuente"] == "redis" and r.get("status") == 404) for r in resultados)
    print(f"Evidencia: {out}")
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())

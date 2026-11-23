#!/usr/bin/env python3
"""Hito 13 - Validación offline (sin Docker) y escaneo de secretos (RNF2, RNF6, RNF8).

Este script NO genera evidencia observada. Sirve para comprobar, sin levantar
contenedores, que la configuración y el colector de métricas son coherentes:

1. Valida la configuración estática: jobs de `prometheus.yml`, reglas de
   `prometheus/reglas-o-alertas.yml` y paneles del dashboard de Grafana.
2. Ejecuta el colector real `app/core/metricas.py` con un diagnóstico SINTÉTICO
   (valores fijos, sin bases reales) en tres fases (normal / Redis caído /
   recuperado) y comprueba la salida en formato Prometheus.
3. Escanea el Hito 13 en busca de secretos.

Todo lo que escribe va a `evidencia/simulacion_sin_docker/` y está rotulado como
SIMULACIÓN (RNF8). La evidencia observada (targets reales y prueba de falla con
`docker stop`/`docker start`) solo la generan `verificar_targets.py --guardar` y
`ejecutar_prueba_controlada.py --guardar` con el entorno levantado.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DIR_HITO13 = Path(__file__).resolve().parents[1]
RAIZ_REPO = DIR_HITO13.parent
DIR_API = RAIZ_REPO / "fixture2030-hito-10-api-integrada"
DIR_SIMULACION = DIR_HITO13 / "evidencia" / "simulacion_sin_docker"
DIR_SECRETOS = DIR_HITO13 / "evidencia" / "resultados_sin_secretos"

sys.path.insert(0, str(DIR_API))
from app.core.metricas import MOTORES, RegistroMetricas  # noqa: E402

AVISO = (
    "SIMULACIÓN SIN DOCKER (RNF8): valores sintéticos fijos procesados por el colector real "
    "app/core/metricas.py. NO fueron observados en Prometheus ni en Grafana y no deben "
    "presentarse como medición."
)


@dataclass
class _DepSalud:
    nombre: str
    estado: str
    latencia_ms: float | None
    motivo: str | None = None


@dataclass
class _DiagSalud:
    estado: str
    dependencias: list[_DepSalud]


# Valores sintéticos de entrada (tomados como referencia de las mediciones del Hito 11).
LATENCIAS_SINTETICAS_MS = {
    "mongodb": 3.5,
    "neo4j": 5.9,
    "cassandra": 77.2,
    "redis": 1.2,
    "influxdb": 34.2,
    "iris": 3.3,
}

OPERACIONES_POR_MOTOR = [
    ("mongodb", "obtener_equipo", "/equipos/{codigo_iso}"),
    ("neo4j", "eventos_partido", "/partidos/{codigo_partido}/eventos"),
    ("cassandra", "leer_muro", "/partidos/{codigo_partido}/comentarios"),
    ("redis", "leer_sesion", "/sesiones/{id_sesion}"),
    ("influxdb", "serie_partido", "/partidos/{codigo_partido}/estadisticas"),
    ("iris", "obtener_acta", "/partidos-oficiales/{codigo_partido}"),
]


def _diagnostico(caidos: set[str] | None = None) -> _DiagSalud:
    caidos = caidos or set()
    deps = [
        _DepSalud(m, "down", None, "DEPENDENCIA_NO_DISPONIBLE")
        if m in caidos
        else _DepSalud(m, "up", LATENCIAS_SINTETICAS_MS[m])
        for m in MOTORES
    ]
    return _DiagSalud("degraded" if caidos else "up", deps)


def _validar_configuracion() -> list[str]:
    """Chequeos estáticos de configuración (no requieren servicios activos)."""
    resultados: list[str] = []

    prom = (DIR_HITO13 / "prometheus.yml").read_text(encoding="utf-8")
    jobs = re.findall(r"job_name:\s*(\S+)", prom)
    assert jobs == ["prometheus", "node-exporter", "fixture-api"], jobs
    assert "scrape_interval: 15s" in prom
    resultados.append(f"prometheus.yml: jobs {jobs}, scrape_interval 15s")

    reglas = (DIR_HITO13 / "prometheus" / "reglas-o-alertas.yml").read_text(encoding="utf-8")
    nombres = re.findall(r"alert:\s*(\S+)", reglas)
    assert len(nombres) == 4, nombres
    resultados.append(f"reglas-o-alertas.yml: {len(nombres)} alertas {nombres}")

    dash = json.loads((DIR_HITO13 / "grafana" / "dashboards" / "fixture2030_war_room.json").read_text(encoding="utf-8"))
    paneles = [p for p in dash.get("panels", []) if p.get("type") != "row"]
    assert len(paneles) == 8, f"Se esperaban 8 paneles de datos y se encontraron {len(paneles)}"
    for p in paneles:
        assert p.get("title"), "panel sin título"
        assert p.get("fieldConfig", {}).get("defaults", {}).get("unit"), f"panel sin unidad: {p['title']}"
    resultados.append(f"fixture2030_war_room.json: {len(paneles)} paneles con título y unidad")

    compose = (DIR_HITO13 / "docker-compose.yml").read_text(encoding="utf-8")
    assert ":latest" not in compose, "docker-compose.yml usa imágenes :latest"
    resultados.append("docker-compose.yml: imágenes con versión fija")
    return resultados


def _simular_tres_fases() -> dict:
    reg = RegistroMetricas()

    # Fase 1: tráfico normal (5 lecturas por motor) + un 400 y un 404 de cliente.
    for motor, op, ruta in OPERACIONES_POR_MOTOR:
        dur_s = LATENCIAS_SINTETICAS_MS[motor] / 1000
        for _ in range(5):
            reg.iniciar_request()
            reg.registrar_operacion_db(motor, op, "ok", dur_s)
            reg.finalizar_request("GET", ruta, 200, dur_s + 0.0008)
    for status, codigo in ((400, "VALIDACION"), (404, "RECURSO_NO_ENCONTRADO")):
        reg.iniciar_request()
        reg.finalizar_request("GET", "/equipos/{codigo_iso}", status, 0.002)
        reg.registrar_error_http("GET", "/equipos/{codigo_iso}", codigo)
    prom_f1 = reg.exportar_prometheus(_diagnostico())
    for m in MOTORES:
        assert f'fixture_db_up{{db="{m}"}} 1' in prom_f1

    # Fase 2: Redis caído -> 503 aislado; MongoDB sigue respondiendo 200.
    for _ in range(3):
        reg.iniciar_request()
        reg.registrar_operacion_db("redis", "leer_sesion", "DEPENDENCIA_NO_DISPONIBLE:ConnectionError", 0.015)
        reg.finalizar_request("GET", "/sesiones/{id_sesion}", 503, 0.016)
        reg.registrar_error_http("GET", "/sesiones/{id_sesion}", "DEPENDENCIA_NO_DISPONIBLE")
        reg.iniciar_request()
        reg.registrar_operacion_db("mongodb", "obtener_equipo", "ok", 0.0034)
        reg.finalizar_request("GET", "/equipos/{codigo_iso}", 200, 0.0041)
    prom_f2 = reg.exportar_prometheus(_diagnostico(caidos={"redis"}))
    assert 'fixture_db_up{db="redis"} 0' in prom_f2
    assert 'fixture_db_up{db="mongodb"} 1' in prom_f2
    assert 'fixture_db_ping_latency_seconds{db="redis"}' not in prom_f2
    assert (
        'fixture_api_http_errors_total{method="GET",route="/sesiones/{id_sesion}",codigo="DEPENDENCIA_NO_DISPONIBLE"} 3'
        in prom_f2
    )

    # Fase 3: recuperación.
    prom_f3 = reg.exportar_prometheus(_diagnostico())
    assert 'fixture_db_up{db="redis"} 1' in prom_f3

    return {"fase_1_normal": prom_f1, "fase_2_redis_caido": prom_f2, "fase_3_recuperado": prom_f3}


def _escanear_secretos() -> tuple[int, list[str]]:
    patrones = [
        re.compile(r"apiv3_[A-Za-z0-9_\-]{15,}"),  # token real de InfluxDB 3
        re.compile(r"(mongodb|redis|neo4j|bolt)://[^/\s:@]+:[^@\s<]+@"),  # URI con contraseña
        re.compile(r"(NEO4J|MONGO|IRIS|GRAFANA_ADMIN)_PASSWORD=(?!\$|<)[^\s]+"),  # se permiten $VAR y <placeholder>
        re.compile(r"GF_SECURITY_ADMIN_PASSWORD:\s*(?!\$\{)\S+"),  # contraseña literal en compose
    ]
    este_archivo = Path(__file__).resolve()
    revisados = 0
    hallazgos: list[str] = []
    for ruta in sorted(DIR_HITO13.rglob("*")):
        if not ruta.is_file() or "__pycache__" in ruta.parts or ruta.resolve() == este_archivo:
            continue
        if ruta.name == ".env":  # archivo local ignorado por git
            continue
        revisados += 1
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for pat in patrones:
            if pat.search(texto):
                hallazgos.append(f"{ruta.relative_to(DIR_HITO13)}: coincide con {pat.pattern}")
    return revisados, hallazgos


def main() -> int:
    ahora = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    DIR_SIMULACION.mkdir(parents=True, exist_ok=True)
    DIR_SECRETOS.mkdir(parents=True, exist_ok=True)

    config = _validar_configuracion()
    fases = _simular_tres_fases()
    for nombre, texto in fases.items():
        (DIR_SIMULACION / f"metrics_{nombre}.prom").write_text(f"# {AVISO}\n{texto}", encoding="utf-8")

    resumen = {
        "generado_en_utc": ahora,
        "tipo": "simulacion_sin_docker",
        "aviso_rnf8": AVISO,
        "validacion_configuracion": config,
        "simulacion": {
            "entrada": "diagnóstico sintético; Redis marcado como down en la fase 2",
            "comprobado": [
                'fase 1: fixture_db_up == 1 para las 6 bases',
                'fase 2: fixture_db_up{db="redis"} == 0, mongodb sigue en 1, sin latencia de ping para redis, '
                "3 errores DEPENDENCIA_NO_DISPONIBLE en /sesiones/{id_sesion}",
                'fase 3: fixture_db_up{db="redis"} vuelve a 1',
            ],
            "no_comprobado": [
                "scraping real de Prometheus (targets, lastScrape, duración)",
                "estado de las alertas en Prometheus",
                "comportamiento real de la API y de los contenedores ante docker stop/start",
            ],
        },
    }
    (DIR_SIMULACION / "resumen_simulacion.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    revisados, hallazgos = _escanear_secretos()
    reporte = (
        "======================================================================\n"
        "VERIFICACIÓN AUTOMATIZADA DE AUSENCIA DE SECRETOS (RNF6 - HITO 13)\n"
        "======================================================================\n"
        f"Fecha UTC:           {ahora}\n"
        "Directorio:          fixture2030-hito-13-monitoreo/ (excluye .env local, ignorado por git)\n"
        f"Archivos escaneados: {revisados}\n"
        "Patrones buscados:   tokens InfluxDB (apiv3_*), URIs con credenciales,\n"
        "                     *_PASSWORD= con valor literal, GF_SECURITY_ADMIN_PASSWORD literal.\n"
        f"Resultado:           {len(hallazgos)} HALLAZGOS {'(OK)' if not hallazgos else '(REVISAR)'}\n"
        + "".join(f"  - {h}\n" for h in hallazgos)
        + "Nota: la contraseña de Grafana se lee de .env (GRAFANA_ADMIN_PASSWORD), que no se versiona.\n"
        "======================================================================\n"
    )
    (DIR_SECRETOS / "verificacion_secretos.txt").write_text(reporte, encoding="utf-8")

    print("Validación de configuración:")
    for linea in config:
        print(f"  - {linea}")
    print(f"\nSimulación de 3 fases OK -> {DIR_SIMULACION.relative_to(DIR_HITO13)}/ ({AVISO})\n")
    print(reporte)
    return 1 if hallazgos else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pruebas unitarias para la persistencia asíncrona de logs en Cassandra y sus endpoints."""

import logging
import threading
import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.adapters.base import operacion
from app.config.settings import Settings
from app.core.errores import DependenciaNoDisponible
from app.core.logs_cassandra import EventoLog, PersistorLogsCassandra
from app.core.metricas import metricas
from app.dependencias import Adaptadores
from app.main import crear_app


def _settings_logs(**cambios) -> Settings:
    base = {
        "logs_cassandra_enabled": True,
        "logs_cassandra_flush_interval_s": 0.05,
        "logs_cassandra_batch_size": 10,
        "logs_cassandra_queue_size": 200,
    }
    return Settings(_env_file=None, **{**base, **cambios})


def _esperar(condicion, timeout_s: float = 2.0) -> None:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        if condicion():
            return
        time.sleep(0.02)
    assert condicion()


def test_logs_http_y_adaptador_se_persisten_en_cassandra_con_request_id(adaptadores: Adaptadores):
    metricas.reiniciar()
    original = adaptadores.mongodb.obtener_equipo

    def obtener_con_operacion(codigo_iso: str):
        with operacion("mongodb", "obtener_equipo", lambda _exc: None):
            return original(codigo_iso)

    adaptadores.mongodb.obtener_equipo = obtener_con_operacion  # type: ignore[method-assign]

    app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/equipos/ARG", headers={"X-Request-ID": "traza-abc-123"})
        assert r.status_code == 200
        _esperar(lambda: len(adaptadores.cassandra.logs_por_request) >= 2)

        traza = [f for f in adaptadores.cassandra.logs_por_request if f["request_id"] == "traza-abc-123"]
        assert len(traza) == 2
        # Orden cronológico (ASC): primero el adaptador MongoDB, luego el acceso HTTP
        assert traza[0]["logger"] == "fixture2030.adaptador"
        assert traza[0]["dependencia"] == "mongodb"
        assert traza[0]["operacion"] == "obtener_equipo"
        assert traza[0]["resultado"] == "ok"

        assert traza[1]["logger"] == "fixture2030.acceso"
        assert traza[1]["metodo"] == "GET"
        assert traza[1]["ruta"] == "/equipos/ARG"
        assert traza[1]["status_http"] == 200
        assert traza[1]["duracion_ms"] is not None

        # api_iniciada no tiene request_id (default '-'): vive en logs_por_hora pero no en logs_por_request
        sin_req = [f for f in adaptadores.cassandra.logs_por_request if f["request_id"] == "-"]
        assert sin_req == []
        assert any("api_iniciada" in f["mensaje"] for f in adaptadores.cassandra.logs_por_hora)


def test_logs_por_nivel_solo_persiste_warning_error_critical(adaptadores: Adaptadores):
    metricas.reiniciar()
    original = adaptadores.mongodb.obtener_equipo

    def obtener_con_operacion(codigo_iso: str):
        with operacion("mongodb", "obtener_equipo", lambda _exc: None):
            return original(codigo_iso)

    adaptadores.mongodb.obtener_equipo = obtener_con_operacion  # type: ignore[method-assign]

    app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/equipos/ARG", headers={"X-Request-ID": "req-ok-1"}).status_code == 200
        adaptadores.mongodb.falla = DependenciaNoDisponible("mongodb")
        assert c.get("/equipos/ARG", headers={"X-Request-ID": "req-warn-1"}).status_code == 503
        adaptadores.mongodb.falla = RuntimeError("fallo inesperado")
        assert c.get("/equipos/ARG", headers={"X-Request-ID": "req-err-1"}).status_code == 500

        _esperar(lambda: len(adaptadores.cassandra.logs_por_nivel) >= 2)
        niveles = {f["nivel"] for f in adaptadores.cassandra.logs_por_nivel}
        assert niveles <= {"WARNING", "ERROR", "CRITICAL"}
        assert "INFO" not in niveles
        assert any(
            f["request_id"] == "req-warn-1" and f["nivel"] == "WARNING" and f["dependencia"] == "mongodb"
            for f in adaptadores.cassandra.logs_por_nivel
        )
        assert any(
            f["request_id"] == "req-err-1" and f["nivel"] == "ERROR" and f["status_http"] == 500
            for f in adaptadores.cassandra.logs_por_nivel
        )


def test_backpressure_cola_llena_no_bloquea_y_contabiliza_descarte():
    metricas.reiniciar()
    bloqueado = threading.Event()
    en_curso = threading.Event()

    class EscritorLento:
        def escribir_lote_logs(self, eventos, ttl_s):
            en_curso.set()
            bloqueado.wait(timeout=2.0)
            return len(eventos)

    persistor = PersistorLogsCassandra(
        escritor=EscritorLento(),
        queue_size=3,
        batch_size=1,
        flush_interval_s=0.05,
    )
    persistor.iniciar()
    ahora = datetime.now(UTC)
    ev = EventoLog(
        creado_en=ahora,
        ventana_hora=ahora.strftime("%Y%m%d%H"),
        fecha=ahora.strftime("%Y%m%d"),
        servicio="fixture2030-api",
        nivel="INFO",
        logger="fixture2030.test",
        request_id="req-bp",
        metodo="GET",
        ruta="/test",
        status_http=200,
        dependencia=None,
        operacion=None,
        resultado="ok",
        duracion_ms=1.0,
        mensaje="evento",
        instancia="test-host",
    )
    try:
        assert persistor.encolar(ev) is True
        assert en_curso.wait(timeout=1.0)
        # Llena la cola (maxsize=3) mientras el worker está bloqueado escribiendo el 1ro
        aceptados = [persistor.encolar(ev) for _ in range(10)]
        assert False in aceptados
    finally:
        bloqueado.set()
        persistor.cerrar(timeout_s=1.0)

    prom = metricas.exportar_prometheus()
    assert 'fixture_api_logs_dropped_total{reason="queue_full"}' in prom


def test_fallo_en_cassandra_no_rompe_api_ni_genera_recursion(adaptadores: Adaptadores, capsys):
    metricas.reiniciar()
    adaptadores.cassandra.falla_logs = RuntimeError("cassandra caida")
    app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/equipos/ARG", headers={"X-Request-ID": "req-caida"})
        assert r.status_code == 200
        _esperar(lambda: 'fixture_api_logs_dropped_total{reason="cassandra_error"}' in metricas.exportar_prometheus())

    captura = capsys.readouterr()
    assert "cassandra_error" in metricas.exportar_prometheus()
    assert "RuntimeError" in captura.err


def test_graceful_shutdown_vacia_cola_incluyendo_api_detenida(adaptadores: Adaptadores):
    metricas.reiniciar()
    app = crear_app(adaptadores=adaptadores, settings=_settings_logs(logs_cassandra_flush_interval_s=0.5))
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/health/live").status_code == 200
    # Al salir del context manager, cerrar() ya hizo flush síncrono de toda la cola.
    assert any("api_detenida" in f["mensaje"] for f in adaptadores.cassandra.logs_por_hora)


def test_endpoints_consulta_logs_y_validacion(adaptadores: Adaptadores):
    metricas.reiniciar()
    original = adaptadores.mongodb.obtener_equipo

    def obtener_con_operacion(codigo_iso: str):
        with operacion("mongodb", "obtener_equipo", lambda _exc: None):
            return original(codigo_iso)

    adaptadores.mongodb.obtener_equipo = obtener_con_operacion  # type: ignore[method-assign]

    app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
    ahora = datetime.now(UTC)
    ventana_actual = ahora.strftime("%Y%m%d%H")
    fecha_actual = ahora.strftime("%Y%m%d")

    with TestClient(app, raise_server_exceptions=False) as c:
        c.get("/equipos/ARG", headers={"X-Request-ID": "consulta-logs-1"})
        adaptadores.mongodb.falla = DependenciaNoDisponible("mongodb")
        c.get("/equipos/ARG", headers={"X-Request-ID": "consulta-logs-err"})
        _esperar(lambda: len(adaptadores.cassandra.logs_por_nivel) >= 1 and len(adaptadores.cassandra.logs_por_hora) >= 4)

        r_hora = c.get("/observabilidad/logs", params={"ventana_hora": ventana_actual, "limit": 20})
        assert r_hora.status_code == 200
        assert r_hora.json()["ventana_hora"] == ventana_actual
        assert len(r_hora.json()["items"]) >= 4

        r_req = c.get("/observabilidad/logs/request/consulta-logs-1")
        assert r_req.status_code == 200
        assert len(r_req.json()["items"]) == 2

        r_err = c.get("/observabilidad/logs/errores", params={"nivel": "WARNING", "fecha": fecha_actual})
        assert r_err.status_code == 200
        assert any(i["request_id"] == "consulta-logs-err" for i in r_err.json()["items"])

        # Validaciones antes de tocar Cassandra
        assert c.get("/observabilidad/logs", params={"ventana_hora": "2030990100"}).status_code == 400
        assert c.get("/observabilidad/logs/errores", params={"nivel": "INFO"}).status_code == 400
        assert c.get("/observabilidad/logs/errores", params={"fecha": "20301301"}).status_code == 400
        assert c.get("/observabilidad/logs/request/-").status_code == 400


def test_metricas_prometheus_incluye_series_de_logs(adaptadores: Adaptadores):
    metricas.reiniciar()
    app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
    with TestClient(app, raise_server_exceptions=False) as c:
        c.get("/equipos/ARG", headers={"X-Request-ID": "req-metrics-logs"})
        _esperar(lambda: len(adaptadores.cassandra.logs_por_hora) >= 2)
        texto = c.get("/metrics").text
        assert "fixture_api_logs_persisted_total " in texto
        assert "fixture_api_logs_queue_size " in texto


def test_logger_raiz_no_acumula_handlers_en_multiples_apps(adaptadores: Adaptadores):
    raiz = logging.getLogger("fixture2030")
    cantidad_inicial = len(raiz.handlers)
    for _ in range(3):
        app = crear_app(adaptadores=adaptadores, settings=_settings_logs())
        with TestClient(app, raise_server_exceptions=False) as c:
            assert c.get("/health/live").status_code == 200
    assert len(raiz.handlers) == cantidad_inicial

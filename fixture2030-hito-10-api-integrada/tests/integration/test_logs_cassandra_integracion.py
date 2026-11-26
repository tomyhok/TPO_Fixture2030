"""Pruebas de integración de persistencia y consulta de logs de la API en Apache Cassandra real."""

import time
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import crear_app

pytestmark = pytest.mark.integracion


def _esperar(condicion, timeout_s: float = 5.0) -> None:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        if condicion():
            return
        time.sleep(0.1)
    assert condicion()


def test_persistencia_y_consulta_logs_en_cassandra_real(settings: Settings):
    if settings.configuracion_faltante()["cassandra"]:
        pytest.skip("Configuración pendiente de Cassandra.")

    req_id = f"it-log-{uuid.uuid4().hex[:12]}"
    ahora = datetime.now(UTC)
    ventana_hora = ahora.strftime("%Y%m%d%H")

    s = settings.model_copy(update={
        "logs_cassandra_enabled": True,
        "logs_cassandra_flush_interval_s": 0.1,
        "logs_cassandra_batch_size": 10,
    })
    app = crear_app(settings=s)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/partidos/P-001/comentarios", params={"ventana": "203006152016"}, headers={"X-Request-ID": req_id})
        assert r.status_code == 200

        def hay_traza() -> bool:
            resp = c.get(f"/observabilidad/logs/request/{req_id}")
            return resp.status_code == 200 and len(resp.json()["items"]) >= 2

        _esperar(hay_traza)

        r_hora = c.get("/observabilidad/logs", params={"ventana_hora": ventana_hora, "limit": 50})
        assert r_hora.status_code == 200
        assert any(item["request_id"] == req_id for item in r_hora.json()["items"])

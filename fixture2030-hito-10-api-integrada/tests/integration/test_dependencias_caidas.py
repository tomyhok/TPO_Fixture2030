"""RF15, RNF9: dependencia no disponible o lenta, con los adaptadores reales.

No hace falta detener contenedores: se configura la API contra puertos donde
no hay nada escuchando (dependencia caída) o contra un servidor que acepta la
conexión y nunca responde (dependencia lenta). En ambos casos la respuesta
debe llegar dentro del timeout y nunca ser un 200 vacío.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from tests.integration.conftest import puerto_libre

pytestmark = pytest.mark.integracion

TIMEOUTS = {"timeout_conexion_s": 1.0, "timeout_operacion_s": 1.0}

RUTAS = {
    "mongodb": "/equipos/ARG",
    "neo4j": "/partidos/P-001/eventos",
    "cassandra": "/partidos/P-001/comentarios?ventana=203006152015",
    "redis": "/sesiones/S-0001",
    "influxdb": "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T21:00:00Z",
    "iris": "/partidos-oficiales/P-001",
}


def _apuntar_a(settings, puerto: int):
    return settings.model_copy(
        update={
            **TIMEOUTS,
            "mongo_port": puerto,
            "neo4j_uri": f"bolt://127.0.0.1:{puerto}",
            "cassandra_port": puerto,
            "redis_port": puerto,
            "influx_url": f"http://127.0.0.1:{puerto}",
            "iris_port": puerto,
        }
    )


@pytest.fixture(scope="module")
def cliente_sin_fuentes(settings):
    app = crear_app(settings=_apuntar_a(settings, puerto_libre()))
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize("fuente", list(RUTAS))
def test_fuente_caida_responde_error_de_dependencia(cliente_sin_fuentes, fuente):
    inicio = time.perf_counter()
    r = cliente_sin_fuentes.get(RUTAS[fuente])
    duracion = time.perf_counter() - inicio
    assert r.status_code in (503, 504)
    error = r.json()["error"]
    assert error["codigo"] in ("DEPENDENCIA_NO_DISPONIBLE", "DEPENDENCIA_TIMEOUT")
    assert error["detalles"] == [{"dependencia": fuente}]
    assert "127.0.0.1" not in r.text and "Traceback" not in r.text
    assert duracion < 10, f"{fuente} tardó {duracion:.1f}s: la request no debe quedar esperando"


def test_health_con_todas_las_fuentes_caidas(cliente_sin_fuentes):
    r = cliente_sin_fuentes.get("/health")
    assert r.status_code == 503
    assert all(d["estado"] in ("caida", "timeout") for d in r.json()["dependencias"])


@pytest.mark.parametrize(
    ("fuente", "campos"),
    [
        ("redis", lambda p: {"redis_port": p}),
        ("influxdb", lambda p: {"influx_url": f"http://127.0.0.1:{p}"}),
        ("mongodb", lambda p: {"mongo_port": p}),
    ],
)
def test_fuente_lenta_corta_por_timeout(settings, servidor_mudo, fuente, campos):
    """Pregunta guía 18: una dependencia que acepta la conexión pero no responde."""
    app = crear_app(settings=settings.model_copy(update={**TIMEOUTS, **campos(servidor_mudo)}))
    with TestClient(app, raise_server_exceptions=False) as c:
        inicio = time.perf_counter()
        r = c.get(RUTAS[fuente])
        duracion = time.perf_counter() - inicio
    assert r.status_code in (503, 504)
    assert r.json()["error"]["detalles"] == [{"dependencia": fuente}]
    assert duracion < 5, f"{fuente} tardó {duracion:.1f}s con timeouts de 1s"

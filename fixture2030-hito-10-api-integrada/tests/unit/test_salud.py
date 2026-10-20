"""Hito 11: liveness, readiness y diagnóstico por dependencia (sección 5.6).

Usan los dobles en memoria: cada estado se provoca asignando `falla` al doble,
igual que lo haría el adaptador real al traducir la excepción del driver.
"""

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.core.errores import DependenciaNoDisponible, DependenciaTimeout
from app.dependencias import Adaptadores
from app.main import crear_app
from tests.unit.conftest import sin_llamadas

FUENTES = {"mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"}


def _settings(**cambios) -> Settings:
    base = {
        "neo4j_password": "x",
        "iris_password": "x",
        "influx_token": "x",
        "health_cache_ttl_s": 60,
    }
    return Settings(_env_file=None, **{**base, **cambios})


@pytest.fixture
def crear_cliente(adaptadores: Adaptadores) -> Iterator:
    clientes: list[TestClient] = []

    def crear(**cambios) -> TestClient:
        app = crear_app(adaptadores=adaptadores, settings=_settings(**cambios))
        c = TestClient(app, raise_server_exceptions=False)
        c.__enter__()
        clientes.append(c)
        return c

    yield crear
    for c in clientes:
        c.__exit__(None, None, None)


def _estados(cuerpo: dict) -> dict[str, str]:
    return {d["nombre"]: d["estado"] for d in cuerpo["dependencias"]}


def test_liveness_no_consulta_ninguna_fuente(crear_cliente, adaptadores):
    r = crear_cliente().get("/health/live")
    assert r.status_code == 200
    assert r.json()["estado"] == "up" and r.json()["version"]
    assert sin_llamadas(adaptadores)


def test_diagnostico_todas_disponibles(crear_cliente):
    r = crear_cliente().get("/health/dependencias")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "up" and cuerpo["desde_cache"] is False
    assert _estados(cuerpo) == {f: "up" for f in FUENTES}


def test_diagnostico_distingue_caida_timeout_y_error_inesperado(crear_cliente, adaptadores):
    adaptadores.mongodb.falla = DependenciaNoDisponible("mongodb")
    adaptadores.redis.falla = DependenciaTimeout("redis")
    adaptadores.cassandra.falla = KeyError("bug")  # no se pudo evaluar: no es "caída"
    cuerpo = crear_cliente().get("/health/dependencias").json()
    por_nombre = {d["nombre"]: d for d in cuerpo["dependencias"]}
    assert cuerpo["estado"] == "degraded"
    assert por_nombre["mongodb"]["estado"] == "down"
    assert por_nombre["mongodb"]["motivo"] == "DEPENDENCIA_NO_DISPONIBLE"
    assert por_nombre["redis"]["motivo"] == "DEPENDENCIA_TIMEOUT"
    assert por_nombre["cassandra"]["estado"] == "unknown"
    assert por_nombre["neo4j"]["estado"] == "up"


def test_fuente_sin_configurar_no_se_consulta(crear_cliente, adaptadores):
    cuerpo = crear_cliente(iris_password="", influx_token="<completar>").get("/health/dependencias").json()
    por_nombre = {d["nombre"]: d for d in cuerpo["dependencias"]}
    assert por_nombre["iris"]["estado"] == "not_configured"
    assert por_nombre["iris"]["motivo"] == "FALTA_CONFIGURACION:IRIS_PASSWORD"
    assert por_nombre["iris"]["latencia_ms"] is None
    assert adaptadores.iris.llamadas == []
    assert por_nombre["influxdb"]["estado"] == "not_configured"
    assert cuerpo["estado"] == "degraded"


def test_fuente_lenta_queda_degraded(crear_cliente, adaptadores):
    adaptadores.neo4j.ping = lambda: time.sleep(0.05)  # type: ignore[method-assign]
    cuerpo = crear_cliente(health_umbral_lento_ms=10).get("/health/dependencias").json()
    neo4j = next(d for d in cuerpo["dependencias"] if d["nombre"] == "neo4j")
    assert neo4j["estado"] == "degraded" and neo4j["motivo"] == "LATENCIA_ALTA"


def test_chequeo_profundo_se_reutiliza_dentro_del_ttl(crear_cliente, adaptadores):
    cliente = crear_cliente()
    cliente.get("/health/dependencias")
    llamadas = len(adaptadores.mongodb.llamadas)
    segunda = cliente.get("/health/dependencias").json()
    assert segunda["desde_cache"] is True
    assert len(adaptadores.mongodb.llamadas) == llamadas  # no volvió a consultar
    tercera = cliente.get("/health/dependencias", params={"refrescar": "true"}).json()
    assert tercera["desde_cache"] is False
    assert len(adaptadores.mongodb.llamadas) == llamadas + 1


def test_ttl_cero_consulta_siempre(crear_cliente, adaptadores):
    cliente = crear_cliente(health_cache_ttl_s=0)
    cliente.get("/health/ready")
    cliente.get("/health/ready")
    assert adaptadores.redis.llamadas == ["ping", "ping"]


def test_readiness_con_una_fuente_caida_sigue_lista(crear_cliente, adaptadores):
    adaptadores.redis.falla = DependenciaNoDisponible("redis")
    r = crear_cliente().get("/health/ready")
    assert r.status_code == 200
    assert r.json()["listo"] is True and r.json()["estado"] == "degraded"
    assert r.json()["no_disponibles"] == ["redis"]


def test_readiness_sin_ninguna_fuente_responde_503(crear_cliente, adaptadores):
    for nombre, doble in adaptadores.como_dict().items():
        doble.falla = DependenciaNoDisponible(nombre)
    r = crear_cliente().get("/health/ready")
    assert r.status_code == 503
    assert r.json()["listo"] is False and r.json()["estado"] == "down"
    assert set(r.json()["no_disponibles"]) == FUENTES


def test_configuracion_faltante_solo_informa_nombres():
    faltantes = Settings(_env_file=None, mongo_user="admin", mongo_password="", neo4j_password="secreto").configuracion_faltante()
    assert "MONGO_PASSWORD" in faltantes["mongodb"]
    assert faltantes["neo4j"] == []
    assert all("secreto" not in v for lista in faltantes.values() for v in lista)

"""RF11, RF12, RF18, RNF9: dependencias caídas, error interno seguro y request ID."""

import uuid

import pytest

from app.core.errores import DependenciaNoDisponible, DependenciaTimeout

# (dependencia que falla, request que la usa)
RUTAS_POR_FUENTE = [
    ("mongodb", "get", "/equipos/ARG"),
    ("neo4j", "get", "/partidos/P-001/eventos"),
    ("cassandra", "get", "/partidos/P-001/comentarios?ventana=203006152016"),
    ("redis", "get", "/sesiones/S-0001"),
    ("influxdb", "get", "/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T21:00:00Z"),
    ("iris", "get", "/partidos-oficiales/P-001"),
]


@pytest.mark.parametrize(("fuente", "metodo", "ruta"), RUTAS_POR_FUENTE)
@pytest.mark.parametrize(
    ("falla", "status", "codigo"),
    [
        (DependenciaNoDisponible, 503, "DEPENDENCIA_NO_DISPONIBLE"),
        (DependenciaTimeout, 504, "DEPENDENCIA_TIMEOUT"),
    ],
)
def test_dependencia_caida_no_se_oculta_en_un_200(cliente, adaptadores, fuente, metodo, ruta, falla, status, codigo):
    getattr(adaptadores, fuente).falla = falla(fuente)
    r = getattr(cliente, metodo)(ruta)
    assert r.status_code == status
    error = r.json()["error"]
    assert error["codigo"] == codigo
    assert error["detalles"] == [{"dependencia": fuente}]


def test_redis_caido_degrada_la_ficha_a_bypass(cliente, adaptadores):
    adaptadores.redis.falla = DependenciaNoDisponible("redis")
    r = cliente.get("/partidos/P-001")
    assert r.status_code == 200
    assert r.headers["X-Cache"] == "BYPASS"


def test_neo4j_caido_con_cache_vigente_responde_desde_cache(cliente, adaptadores):
    assert cliente.get("/partidos/P-001").headers["X-Cache"] == "MISS"
    adaptadores.neo4j.falla = DependenciaNoDisponible("neo4j")
    r = cliente.get("/partidos/P-001")
    assert r.status_code == 200 and r.headers["X-Cache"] == "HIT"


def test_neo4j_caido_sin_cache_es_503(cliente, adaptadores):
    adaptadores.neo4j.falla = DependenciaNoDisponible("neo4j")
    assert cliente.get("/partidos/P-002").status_code == 503


def test_health_informa_la_fuente_caida(cliente, adaptadores):
    adaptadores.cassandra.falla = DependenciaNoDisponible("cassandra")
    adaptadores.iris.falla = DependenciaTimeout("iris")
    r = cliente.get("/health")
    assert r.status_code == 503
    estados = {d["nombre"]: d["estado"] for d in r.json()["dependencias"]}
    assert estados["cassandra"] == "caida" and estados["iris"] == "timeout" and estados["mongodb"] == "ok"


def test_error_inesperado_no_expone_detalle(cliente, adaptadores):
    adaptadores.mongodb.falla = RuntimeError("mongodb://admin:secreto@host:27017 explotó")
    r = cliente.get("/equipos/ARG")
    assert r.status_code == 500
    assert r.json()["error"]["codigo"] == "ERROR_INTERNO"
    assert "secreto" not in r.text and "mongodb://" not in r.text


def test_request_id_se_genera_y_se_reutiliza(cliente):
    generado = cliente.get("/equipos/XYZ")
    rid = generado.headers["X-Request-ID"]
    assert uuid.UUID(rid) and generado.json()["error"]["request_id"] == rid
    propio = cliente.get("/equipos/XYZ", headers={"X-Request-ID": "prueba-123"})
    assert propio.headers["X-Request-ID"] == "prueba-123"
    assert propio.json()["error"]["request_id"] == "prueba-123"
    inseguro = cliente.get("/equipos/ARG", headers={"X-Request-ID": "<script>"})
    assert inseguro.headers["X-Request-ID"] != "<script>"


def test_ruta_y_metodo_inexistentes_usan_el_formato_comun(cliente):
    assert cliente.get("/no-existe").json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"
    r = cliente.put("/equipos/ARG")
    assert r.status_code == 405 and r.json()["error"]["codigo"] == "METODO_NO_PERMITIDO"

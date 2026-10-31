"""Hito 13: pruebas unitarias del endpoint /metrics y del registro Prometheus."""

from app.core.errores import DependenciaNoDisponible, DependenciaTimeout
from app.core.metricas import metricas


def test_metrics_expone_formato_prometheus_y_estado_de_seis_bases(cliente, adaptadores):
    metricas.reiniciar()
    r = cliente.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain; version=0.0.4")
    texto = r.text
    assert "fixture_api_up 1" in texto
    for motor in ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"):
        assert f'fixture_db_up{{db="{motor}"}} 1' in texto
        assert f'fixture_db_status_info{{db="{motor}",state="up"}} 1' in texto


def test_metrics_registra_requests_errores_y_latencias(cliente, adaptadores):
    metricas.reiniciar()
    assert cliente.get("/equipos/ARG").status_code == 200
    assert cliente.get("/equipos/XYZ").status_code == 404
    assert cliente.get("/equipos/arg").status_code == 400

    adaptadores.mongodb.falla = DependenciaNoDisponible("mongodb")
    assert cliente.get("/equipos/ARG").status_code == 503

    adaptadores.neo4j.falla = DependenciaTimeout("neo4j")
    assert cliente.get("/partidos/P-001/eventos").status_code == 504

    texto = cliente.get("/metrics").text
    assert 'fixture_api_http_requests_total{method="GET",route="/equipos/{codigo_iso}",status="200"} 1' in texto
    assert 'fixture_api_http_requests_total{method="GET",route="/equipos/{codigo_iso}",status="404"} 1' in texto
    assert 'fixture_api_http_requests_total{method="GET",route="/equipos/{codigo_iso}",status="400"} 1' in texto
    assert 'fixture_api_http_requests_total{method="GET",route="/equipos/{codigo_iso}",status="503"} 1' in texto
    assert 'fixture_api_http_errors_total{method="GET",route="/equipos/{codigo_iso}",codigo="RECURSO_NO_ENCONTRADO"} 1' in texto
    assert 'fixture_api_http_errors_total{method="GET",route="/equipos/{codigo_iso}",codigo="VALIDACION_ERROR"} 1' in texto
    assert 'fixture_api_http_errors_total{method="GET",route="/equipos/{codigo_iso}",codigo="DEPENDENCIA_NO_DISPONIBLE"} 1' in texto
    assert 'fixture_api_http_errors_total{method="GET",route="/partidos/{codigo_partido}/eventos",codigo="DEPENDENCIA_TIMEOUT"} 1' in texto
    assert 'fixture_api_http_request_duration_seconds_count{method="GET",route="/equipos/{codigo_iso}"} 4' in texto


def test_metrics_refleja_base_caida_y_operaciones_de_adaptador(cliente, adaptadores):
    metricas.reiniciar()
    metricas.registrar_operacion_db("mongodb", "obtener_equipo", "ok", 0.004)
    metricas.registrar_operacion_db("redis", "leer_sesion", "DEPENDENCIA_NO_DISPONIBLE:ConnectionError", 0.012)

    adaptadores.redis.falla = DependenciaNoDisponible("redis")
    cliente.get("/health/dependencias", params={"refrescar": "true"})

    texto = cliente.get("/metrics").text
    assert 'fixture_db_up{db="redis"} 0' in texto
    assert 'fixture_db_status_info{{db="redis",state="down"}} 1'.format() in texto
    assert 'fixture_db_operations_total{db="mongodb",operation="obtener_equipo",status="ok"} 1' in texto
    assert 'fixture_db_operations_total{db="redis",operation="leer_sesion",status="DEPENDENCIA_NO_DISPONIBLE"} 1' in texto
    assert 'fixture_db_operation_duration_seconds_count{db="mongodb",operation="obtener_equipo"} 1' in texto

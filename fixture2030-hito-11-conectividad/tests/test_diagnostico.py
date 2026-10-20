"""Pruebas unitarias del diagnóstico (sin bases de datos).

Uso (desde la raíz del repositorio):
    fixture2030-hito-10-api-integrada/.venv/Scripts/python -m pytest fixture2030-hito-11-conectividad/tests -q
"""

import io
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from conectividad import api  # noqa: E402
from conectividad.config import Config  # noqa: E402
from conectividad.productos import cassandra  # noqa: E402
from conectividad.red import probar_tcp, puerto_cerrado, resolver  # noqa: E402
from conectividad.registro import (  # noqa: E402
    FAIL,
    OK,
    SKIP,
    WARN,
    Cadena,
    Redactor,
    Registro,
    Resultado,
    estado_producto,
    fail,
    ok,
)


def _cfg(**valores: str) -> Config:
    # HITO10_ENV inexistente: las pruebas no dependen del .env local.
    return Config({"HITO10_ENV": "/no/existe/.env", **valores})


def _registro() -> Registro:
    return Registro(Redactor([]), salida=io.StringIO())


def _r(capa: str, estado: str, **datos) -> Resultado:
    return Resultado("p", capa, "prueba", estado, "detalle", "destino", "t", 1.0, datos=datos)


# ------------------------------------------------------------- secretos
def test_secretos_nunca_se_muestran():
    cfg = _cfg(MONGO_PASSWORD="s3creto-largo", IRIS_PASSWORD="<completar>")
    assert cfg.mostrar("MONGO_PASSWORD") == "(definida, oculta)"
    assert cfg.mostrar("IRIS_PASSWORD") == "(sin completar)"
    assert cfg.mostrar("REDIS_PASSWORD") == "(vacía)"
    assert cfg.mostrar("MONGO_HOST") == "127.0.0.1"


def test_variable_de_entorno_tiene_prioridad_y_se_informa_el_origen():
    cfg = _cfg(MONGO_HOST="mongodb")
    assert cfg.get("MONGO_HOST") == "mongodb"
    assert cfg.origen("MONGO_HOST") == "variable de entorno"
    assert cfg.origen("REDIS_HOST") == "defecto"


def test_secreto_igual_a_identificador_publico_no_se_oculta_por_valor():
    ocultables, publicos = _cfg(NEO4J_PASSWORD="fixture2030", MONGO_PASSWORD="otro-secreto",
                                INFLUX_TOKEN_FILE="/no/existe").secretos()
    assert "fixture2030" not in ocultables and "otro-secreto" in ocultables
    assert publicos == 1


def test_redactor():
    r = Redactor(["s3creto-largo"])
    texto = r("pwd s3creto-largo mongodb://admin:clave@h:1 Authorization: Bearer abc.def "
              "password=xyz {\"token\": \"t\"} C:\\Users\\ana\\x /c/Users/ana/y database=fixture2030")
    for secreto in ("s3creto-largo", "clave", "abc.def", "xyz", '"t"', "ana"):
        assert secreto not in texto
    assert "database=fixture2030" in texto and "mongodb://admin:***@h:1" in texto


# ------------------------------------------------------------- matriz
def test_solo_tcp_no_alcanza_para_declarar_disponible():
    estado, _ = estado_producto([_r("configuracion", OK), _r("resolucion", OK), _r("tcp", OK)])
    assert estado == "desconocido"


def test_falla_en_la_cadena_es_no_disponible():
    estado, diag = estado_producto([_r("tcp", OK), _r("protocolo", FAIL), _r("lectura", SKIP)])
    assert estado == "no disponible" and "protocolo" in diag


def test_nativo_ok_y_api_fallando_es_degradado():
    rs = [_r(c, OK) for c in ("tcp", "protocolo", "lectura")] + [_r("api", FAIL)]
    assert estado_producto(rs)[0] == "degradado"


def test_lectura_lenta_es_degradado_y_ausencia_valida_no():
    base = [_r(c, OK) for c in ("tcp", "protocolo")]
    assert estado_producto(base + [_r("lectura", WARN, degrada=True)])[0] == "degradado"
    assert estado_producto(base + [_r("lectura", WARN)])[0] == "disponible"


def test_no_configurado_y_no_probado():
    assert estado_producto([_r("configuracion", WARN, no_configurado=True), _r("tcp", SKIP)])[0] == "no configurado"
    assert estado_producto([_r("tcp", SKIP), _r("lectura", SKIP)])[0] == "no probado"


def test_capa_fallida_bloquea_las_siguientes():
    reg = _registro()
    c = Cadena(reg, "p", {"tcp", "protocolo", "lectura", "sonda"}, "d", lambda e, capa: fail("x", "h", "s"))
    c.ejecutar("tcp", "t", lambda: fail("refused", "h", "s"))
    c.ejecutar("protocolo", "p", lambda: ok("no debería correr"))
    c.ejecutar("sonda", "s", lambda: ok("las secundarias no se bloquean"))
    assert [r.estado for r in reg.resultados] == [FAIL, SKIP, OK]


def test_excepcion_se_clasifica_y_no_se_oculta():
    reg = _registro()
    c = Cadena(reg, "p", {"protocolo"}, "d", lambda e, capa: fail(f"{type(e).__name__}", "h", "s"))
    c.ejecutar("protocolo", "p", lambda: 1 / 0)
    assert reg.resultados[0].estado == FAIL and "ZeroDivisionError" in reg.resultados[0].detalle


# ------------------------------------------------------------- red
def test_tcp_listener_y_puerto_cerrado():
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        assert probar_tcp(["127.0.0.1"], servidor.getsockname()[1], 3, "X").estado == OK
    paso = probar_tcp(["127.0.0.1"], puerto_cerrado(), 3, "X_PORT")
    assert paso.estado == FAIL and paso.datos["clase_tcp"] in ("refused", "timeout")


def test_ip_literal_no_requiere_dns_y_host_inexistente_falla():
    assert resolver("127.0.0.1", 1).estado == OK
    assert resolver("host-inexistente-h11.invalid", 1).estado == FAIL


# ------------------------------------------------------------- API
@pytest.mark.parametrize(
    ("status", "cuerpo", "esperado"),
    [
        (200, {"nombre": "Argentina"}, api.EXITO),
        (200, {"items": []}, api.VACIO),
        (400, {}, api.VALIDACION),
        (404, {}, api.INEXISTENTE),
        (503, {}, api.NO_DISPONIBLE),
        (504, {}, api.TIMEOUT),
        (500, {}, api.INTERNO),
    ],
)
def test_clasificacion_de_respuestas_de_la_api(status, cuerpo, esperado):
    assert api.clasificar(status, cuerpo) == esperado

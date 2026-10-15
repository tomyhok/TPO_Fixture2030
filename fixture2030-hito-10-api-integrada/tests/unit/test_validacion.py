"""RF10 / RNF3: una entrada inválida responde 400 y no llega a ninguna fuente."""

import uuid

import pytest

from tests.unit.conftest import sin_llamadas

COMENTARIO_OK = {
    "id_usuario": "U-1001",
    "usuario_alias": "hincha_albiceleste",
    "equipo_apoyado": "ARG",
    "texto": "Vamos",
    "idioma": "es",
    "minuto_partido": 10,
}

CASOS_GET = [
    ("/equipos/arg", "path.codigo_iso"),
    ("/equipos/ARGE", "path.codigo_iso"),
    ("/equipos?size=0", "query.size"),
    ("/equipos?size=51", "query.size"),
    ("/equipos?confederacion=FIFA", "query.confederacion"),
    ("/equipos?grupo=Z", "query.grupo"),
    ("/equipos/ARG/jugadores?posicion=Arquero", "query.posicion"),
    ("/jugadores/ARG10", "path.id_jugador"),
    ("/partidos/P1", "path.codigo_partido"),
    ("/partidos/P-001/eventos?limit=500", "query.limit"),
    ("/equipos/ARG/rivales?limit=0", "query.limit"),
    ("/partidos/P-001/comentarios", "query.ventana"),
    ("/partidos/P-001/comentarios?ventana=2030", "query.ventana"),
    ("/partidos/P-001/comentarios?ventana=203013152015", "query.ventana"),
    ("/partidos/P-001/comentarios?ventana=203006152016&cursor=abc", "query.cursor"),
    (f"/partidos/P-001/comentarios?ventana=203006152016&cursor={uuid.uuid4()}", "query.cursor"),
    ("/partidos/P-001/comentarios?ventana=203006152016&limit=101", "query.limit"),
    ("/sesiones/abc", "path.id_sesion"),
    ("/partidos/P-001/estadisticas?hasta=2030-06-10T21:00:00Z", "query.desde"),
    ("/partidos/P-001/estadisticas?desde=ayer&hasta=2030-06-10T21:00:00Z", "query.desde"),
    ("/partidos/P-001/estadisticas?desde=2030-06-10T22:00:00Z&hasta=2030-06-10T20:00:00Z", "query.desde"),
    ("/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T23:00:01Z", "query.hasta"),
    ("/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00&hasta=2030-06-10T21:00:00", "query.desde"),
    ("/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T21:00:00Z&resolucion=1h", "query.resolucion"),
    ("/partidos-oficiales/p-001", "path.codigo_partido"),
]


@pytest.mark.parametrize(("ruta", "campo"), CASOS_GET)
def test_get_invalido_responde_400_sin_consultar(cliente, adaptadores, ruta, campo):
    r = cliente.get(ruta)
    assert r.status_code == 400
    error = r.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert campo in [d["campo"] for d in error["detalles"]]
    assert sin_llamadas(adaptadores)


@pytest.mark.parametrize(
    ("cuerpo", "headers", "campo"),
    [
        (COMENTARIO_OK, {}, "header.Idempotency-Key"),
        (COMENTARIO_OK, {"Idempotency-Key": "123"}, "header.Idempotency-Key"),
        ({**COMENTARIO_OK, "texto": ""}, None, "body.texto"),
        ({**COMENTARIO_OK, "texto": "x" * 501}, None, "body.texto"),
        ({**COMENTARIO_OK, "idioma": "fr"}, None, "body.idioma"),
        ({**COMENTARIO_OK, "minuto_partido": 131}, None, "body.minuto_partido"),
        ({**COMENTARIO_OK, "equipo_apoyado": "arg"}, None, "body.equipo_apoyado"),
        ({**COMENTARIO_OK, "estado_moderacion": "publicado"}, None, "body.estado_moderacion"),
    ],
)
def test_post_comentario_invalido(cliente, adaptadores, cuerpo, headers, campo):
    headers = {"Idempotency-Key": str(uuid.uuid4())} if headers is None else headers
    r = cliente.post("/partidos/P-001/comentarios", json=cuerpo, headers=headers)
    assert r.status_code == 400
    assert campo in [d["campo"] for d in r.json()["error"]["detalles"]]
    assert sin_llamadas(adaptadores)


def test_json_malformado(cliente, adaptadores):
    r = cliente.post(
        "/partidos/P-001/comentarios",
        content=b"{no es json",
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 400
    assert sin_llamadas(adaptadores)


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"estado": "Suspendido"}, "body.estado"),
        ({}, "body.estado"),
        ({"estado": "En Juego", "motivo": "x"}, "body.motivo"),
    ],
)
def test_patch_estado_invalido(cliente, adaptadores, cuerpo, campo):
    r = cliente.patch("/partidos-oficiales/P-001/estado", json=cuerpo)
    assert r.status_code == 400
    assert campo in [d["campo"] for d in r.json()["error"]["detalles"]]
    assert sin_llamadas(adaptadores)


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"minuto": 0, "tipo": "Gol"}, "body.minuto"),
        ({"minuto": 131, "tipo": "Gol"}, "body.minuto"),
        ({"minuto": 10, "tipo": "Penal"}, "body.tipo"),
        ({"minuto": 10, "tipo": "Gol", "descripcion": "x" * 201}, "body.descripcion"),
    ],
)
def test_post_evento_acta_invalido(cliente, adaptadores, cuerpo, campo):
    r = cliente.post(
        "/partidos-oficiales/P-001/eventos", json=cuerpo, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert r.status_code == 400
    assert campo in [d["campo"] for d in r.json()["error"]["detalles"]]
    assert sin_llamadas(adaptadores)

"""RF19, RNF14: escrituras repetidas por reintentos no duplican datos."""

import json
import uuid

from app.core.errores import DependenciaNoDisponible

COMENTARIO = {
    "id_usuario": "U-1001",
    "usuario_alias": "hincha",
    "equipo_apoyado": "ARG",
    "texto": "Vamos",
    "idioma": "es",
    "minuto_partido": 10,
}


def _post(cliente, cuerpo, clave):
    return cliente.post("/partidos/P-001/comentarios", json=cuerpo, headers={"Idempotency-Key": clave})


def test_misma_clave_y_cuerpo_no_duplica(cliente, adaptadores):
    clave = str(uuid.uuid4())
    primera = _post(cliente, COMENTARIO, clave)
    repetida = _post(cliente, COMENTARIO, clave)
    assert primera.status_code == 201 and "Idempotent-Replayed" not in primera.headers
    assert repetida.status_code == 200 and repetida.headers["Idempotent-Replayed"] == "true"
    assert repetida.json() == primera.json()
    assert len(adaptadores.cassandra.publicados) == 1


def test_clave_en_mayusculas_es_la_misma(cliente, adaptadores):
    clave = str(uuid.uuid4())
    _post(cliente, COMENTARIO, clave)
    assert _post(cliente, COMENTARIO, clave.upper()).status_code == 200
    assert len(adaptadores.cassandra.publicados) == 1


def test_misma_clave_con_otro_cuerpo_es_409(cliente, adaptadores):
    clave = str(uuid.uuid4())
    _post(cliente, COMENTARIO, clave)
    r = _post(cliente, {**COMENTARIO, "texto": "Otro texto"}, clave)
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "CONFLICTO_IDEMPOTENCIA"
    assert len(adaptadores.cassandra.publicados) == 1


def test_clave_en_curso_es_409(cliente, adaptadores):
    clave = str(uuid.uuid4())
    _post(cliente, COMENTARIO, clave)
    registro = json.loads(adaptadores.redis.idem[f"idem:comentario:{clave}"])
    registro["estado"] = "en_curso"
    adaptadores.redis.idem[f"idem:comentario:{clave}"] = json.dumps(registro)
    assert _post(cliente, COMENTARIO, clave).status_code == 409


def test_escritura_fallida_libera_la_clave(cliente, adaptadores):
    clave = str(uuid.uuid4())
    adaptadores.cassandra.falla = DependenciaNoDisponible("cassandra")
    assert _post(cliente, COMENTARIO, clave).status_code == 503
    assert adaptadores.redis.idem == {}
    adaptadores.cassandra.falla = None
    assert _post(cliente, COMENTARIO, clave).status_code == 201  # el reintento sí escribe


def test_sin_redis_no_se_escribe(cliente, adaptadores):
    adaptadores.redis.falla = DependenciaNoDisponible("redis")
    r = _post(cliente, COMENTARIO, str(uuid.uuid4()))
    assert r.status_code == 503
    assert adaptadores.cassandra.publicados == []


def test_claves_distintas_crean_comentarios_distintos(cliente, adaptadores):
    a = _post(cliente, COMENTARIO, str(uuid.uuid4()))
    b = _post(cliente, COMENTARIO, str(uuid.uuid4()))
    assert a.json()["id_comentario"] != b.json()["id_comentario"]
    assert len(adaptadores.cassandra.publicados) == 2


def test_evento_de_acta_repetido_no_duplica(cliente, adaptadores):
    clave = str(uuid.uuid4())
    cuerpo = {"minuto": 70, "tipo": "Tarjeta Roja", "descripcion": "Juego brusco"}
    primera = cliente.post("/partidos-oficiales/P-001/eventos", json=cuerpo, headers={"Idempotency-Key": clave})
    repetida = cliente.post("/partidos-oficiales/P-001/eventos", json=cuerpo, headers={"Idempotency-Key": clave})
    assert (primera.status_code, repetida.status_code) == (201, 200)
    assert len(adaptadores.iris.actas["P-001"]["eventos"]) == 1
    assert adaptadores.iris.llamadas.count("registrar_evento") == 1

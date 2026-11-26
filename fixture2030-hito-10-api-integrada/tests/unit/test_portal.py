"""Portal de demostración (/portal/api): navegación, sesión, muro y estado del partido con dobles."""

from tests.unit.conftest import sin_llamadas

BASE = "/portal/api"


def _login(cliente, alias="hincha_test", equipo="ARG"):
    r = cliente.post(f"{BASE}/sesiones", json={"alias": alias, "equipo_favorito": equipo})
    assert r.status_code == 201
    return r.json()["id_sesion"]


def test_raiz_redirige_al_portal_y_sirve_paginas(cliente):
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/portal/"
    assert cliente.get("/portal/").status_code == 200
    assert cliente.get("/demo/").status_code == 200


def test_navegacion(cliente):
    partidos = cliente.get(f"{BASE}/partidos").json()
    assert partidos[0]["codigo_partido"] == "P-001"
    assert {e["codigo_iso"] for e in partidos[0]["equipos"]} == {"ARG", "ESP"}
    assert partidos[0]["estado"] == "En Juego" and partidos[0]["arbitro"]["apellido"] == "Tello"
    assert len(cliente.get(f"{BASE}/equipos").json()) == 2
    plantel = cliente.get(f"{BASE}/equipos/ARG/plantel").json()
    assert plantel["equipo"]["nombre"] == "Argentina" and plantel["jugadores"][0]["id_jugador"] == "ARG-10"
    assert cliente.get(f"{BASE}/equipos/XYZ/plantel").status_code == 404


def test_sesion_ciclo_completo(cliente):
    id_sesion = _login(cliente)
    datos = cliente.get(f"{BASE}/sesiones/{id_sesion}").json()
    assert datos["alias"] == "hincha_test" and datos["equipo_favorito"] == "ARG"
    assert cliente.delete(f"{BASE}/sesiones/{id_sesion}").status_code == 204
    assert cliente.get(f"{BASE}/sesiones/{id_sesion}").json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_alias_invalido_no_toca_redis(cliente, adaptadores):
    r = cliente.post(f"{BASE}/sesiones", json={"alias": "<script>", "equipo_favorito": None})
    assert r.status_code == 400
    assert sin_llamadas(adaptadores)


def test_comentar_requiere_sesion(cliente, adaptadores):
    r = cliente.post(f"{BASE}/partidos/P-001/comentarios", json={"texto": "hola", "equipo_apoyado": "ARG"})
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "SESION_REQUERIDA"
    assert "publicar_comentario" not in adaptadores.cassandra.llamadas


def test_comentar_y_leer_muro(cliente):
    h = {"X-Sesion-ID": _login(cliente)}
    ajeno = cliente.post(f"{BASE}/partidos/P-001/comentarios", headers=h, json={"texto": "hola", "equipo_apoyado": "BRA"})
    assert ajeno.status_code == 400
    r = cliente.post(f"{BASE}/partidos/P-001/comentarios", headers=h,
                     json={"texto": "Vamos!", "equipo_apoyado": "ARG"})
    assert r.status_code == 201
    assert r.json()["usuario_alias"] == "hincha_test" and r.json()["id_usuario"] == "U-5001"
    assert r.json()["minuto_partido"] is None  # sin simulación en curso no hay minuto
    muro = cliente.get(f"{BASE}/partidos/P-001/muro").json()
    assert len(muro["ventanas"]) == 15 and muro["items"][0]["texto"] == "Vamos!"


def test_visitas_sin_sesion(cliente):
    assert cliente.post(f"{BASE}/partidos/P-001/visitas").json()["visitas"] == 1
    assert cliente.post(f"{BASE}/partidos/P-001/visitas").json()["visitas"] == 2
    assert cliente.post(f"{BASE}/partidos/P-999/visitas").status_code == 404


def test_portal_fuera_del_contrato_openapi(cliente):
    assert not any(p.startswith("/portal") for p in cliente.get("/openapi.json").json()["paths"])


def test_estado_del_partido_solo_avanza(cliente, adaptadores):
    assert cliente.put(f"{BASE}/partidos/P-002/estado", json={"estado": "En Juego"}).status_code == 401
    h = {"X-Sesion-ID": _login(cliente)}
    atras = cliente.put(f"{BASE}/partidos/P-001/estado", headers=h, json={"estado": "Programado"})
    assert atras.status_code == 409 and atras.json()["error"]["codigo"] == "CONFLICTO"
    assert cliente.put(f"{BASE}/partidos/P-001/estado", headers=h, json={"estado": "En Juego"}).status_code == 409
    r = cliente.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"})
    assert r.status_code == 200 and r.json()["estado"] == "En Juego"
    assert cliente.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "Finalizado"}).json()["estado"] == "Finalizado"
    assert cliente.put(f"{BASE}/partidos/P-999/estado", headers=h, json={"estado": "Finalizado"}).status_code == 404
    adaptadores.neo4j.llamadas.clear()
    assert cliente.put(f"{BASE}/partidos/P-001/estado", headers=h, json={"estado": "Suspendido"}).status_code == 400
    assert adaptadores.neo4j.llamadas == []


def test_minuto_del_comentario_sale_del_reloj_de_la_simulacion(cliente, adaptadores):
    h = {"X-Sesion-ID": _login(cliente)}
    adaptadores.redis.relojes["P-001"] = {"minuto": 37, "adicion": 3, "en_curso": True}
    r = cliente.post(f"{BASE}/partidos/P-001/comentarios", headers=h, json={"texto": "Golazo", "equipo_apoyado": "ARG"})
    assert r.status_code == 201 and r.json()["minuto_partido"] == 37
    adaptadores.redis.relojes["P-001"] = {"minuto": 93, "adicion": 3, "en_curso": False}  # ya terminó
    r = cliente.post(f"{BASE}/partidos/P-001/comentarios", headers=h, json={"texto": "Final", "equipo_apoyado": "ARG"})
    assert r.json()["minuto_partido"] is None
    # El minuto ya no se puede mandar desde el cliente.
    r = cliente.post(f"{BASE}/partidos/P-001/comentarios", headers=h,
                     json={"texto": "x", "equipo_apoyado": "ARG", "minuto_partido": 5})
    assert r.status_code == 400

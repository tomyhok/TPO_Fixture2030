"""Portal de demostración (/portal/api): navegación, sesión, muro y encuesta con dobles."""

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
                     json={"texto": "Vamos!", "equipo_apoyado": "ARG", "minuto_partido": 23})
    assert r.status_code == 201
    assert r.json()["usuario_alias"] == "hincha_test" and r.json()["id_usuario"] == "U-5001"
    muro = cliente.get(f"{BASE}/partidos/P-001/muro").json()
    assert len(muro["ventanas"]) == 15 and muro["items"][0]["texto"] == "Vamos!"


def test_encuesta_un_voto_por_usuario(cliente):
    h = {"X-Sesion-ID": _login(cliente)}
    r = cliente.post(f"{BASE}/partidos/P-001/encuesta", headers=h, json={"id_jugador": "ARG-10"})
    assert r.status_code == 200 and r.json()["ya_voto"] and r.json()["encuesta"][0] == {"id_jugador": "ARG-10", "votos": 1}
    otra = cliente.post(f"{BASE}/partidos/P-001/encuesta", headers=h, json={"id_jugador": "ESP-8"})
    assert otra.status_code == 409 and otra.json()["error"]["codigo"] == "CONFLICTO"
    ajeno = cliente.post(f"{BASE}/partidos/P-001/encuesta", headers=h, json={"id_jugador": "BRA-10"})
    assert ajeno.status_code == 400


def test_visitas_sin_sesion(cliente):
    assert cliente.post(f"{BASE}/partidos/P-001/visitas").json()["visitas"] == 1
    assert cliente.post(f"{BASE}/partidos/P-001/visitas").json()["visitas"] == 2
    assert cliente.post(f"{BASE}/partidos/P-999/visitas").status_code == 404


def test_portal_fuera_del_contrato_openapi(cliente):
    assert not any(p.startswith("/portal") for p in cliente.get("/openapi.json").json()["paths"])

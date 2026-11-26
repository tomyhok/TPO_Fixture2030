"""Prode del portal: predicciones, puntajes y tabla de posiciones en MongoDB, con dobles.

En el doble de Neo4j, P-001 está 'En Juego', P-002 'Programado' y P-003 'Finalizado'
con un gol de URU-9 (ESP 0 - 1 URU).
"""

from app.core.errores import DependenciaNoDisponible
from app.services.prode_service import marcador
from tests.unit.conftest import sin_llamadas

BASE = "/portal/api"


def _login(cliente, alias, equipo=None):
    r = cliente.post(f"{BASE}/sesiones", json={"alias": alias, "equipo_favorito": equipo})
    assert r.status_code == 201
    return {"X-Sesion-ID": r.json()["id_sesion"]}, r.json()["usuario_id"]


def _pronosticar(cliente, h, codigo, gl, gv):
    return cliente.put(f"{BASE}/partidos/{codigo}/prediccion", headers=h,
                       json={"goles_local": gl, "goles_visitante": gv})


def test_mismo_alias_recupera_el_mismo_usuario(cliente, adaptadores):
    _, primero = _login(cliente, "Tribuna_Norte", "ARG")
    _, segundo = _login(cliente, "tribuna_norte", "URU")
    assert primero == segundo == "U-5001"
    _, otro = _login(cliente, "otro_hincha")
    assert otro != primero
    assert adaptadores.mongodb.usuarios["tribuna_norte"]["equipo_favorito"] == "URU"


def test_pronosticar_requiere_sesion_y_valida_antes_de_consultar(cliente, adaptadores):
    r = cliente.put(f"{BASE}/partidos/P-002/prediccion", json={"goles_local": 1, "goles_visitante": 0})
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "SESION_REQUERIDA"
    assert "guardar_prediccion" not in adaptadores.mongodb.llamadas
    adaptadores.redis.llamadas.clear()
    for cuerpo in ({"goles_local": -1, "goles_visitante": 0}, {"goles_local": 21, "goles_visitante": 0},
                   {"goles_local": 1}, {"goles_local": 1, "goles_visitante": 0, "puntos": 3}):
        r = cliente.put(f"{BASE}/partidos/P-002/prediccion", json=cuerpo)
        assert r.status_code == 400, cuerpo
    assert sin_llamadas(adaptadores)


def test_pronostico_se_guarda_y_se_puede_corregir(cliente):
    h, uid = _login(cliente, "hincha_uno", "URU")
    r = _pronosticar(cliente, h, "P-002", 2, 1)
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["equipo_local"], p["equipo_visitante"], p["resultado"], p["puntos"]) == ("URU", "ARG", "L", None)
    assert p["usuario_id"] == uid
    corregido = _pronosticar(cliente, h, "P-002", 0, 0).json()
    assert corregido["resultado"] == "E" and corregido["creada_en"] == p["creada_en"]
    mias = cliente.get(f"{BASE}/predicciones", headers=h).json()
    assert len(mias) == 1 and mias[0]["goles_local"] == 0


def test_partido_empezado_no_acepta_pronosticos(cliente):
    h, _ = _login(cliente, "hincha_uno")
    r = _pronosticar(cliente, h, "P-001", 1, 0)  # En Juego
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "PREDICCION_CERRADA"
    assert _pronosticar(cliente, h, "P-999", 1, 0).status_code == 404


def test_neo4j_caido_no_deja_pronosticar(cliente, adaptadores):
    h, _ = _login(cliente, "hincha_uno")
    adaptadores.neo4j.falla = DependenciaNoDisponible("neo4j")
    assert _pronosticar(cliente, h, "P-002", 1, 0).status_code == 503
    assert "guardar_prediccion" not in adaptadores.mongodb.llamadas


def test_resumen_del_partido(cliente):
    for alias, gl, gv in (("a_uno", 2, 1), ("a_dos", 2, 1), ("a_tres", 0, 3)):
        h, _ = _login(cliente, alias)
        assert _pronosticar(cliente, h, "P-002", gl, gv).status_code == 200
    r = cliente.get(f"{BASE}/partidos/P-002/predicciones", headers=h).json()
    assert r["abierta"] and r["estado"] == "Programado"
    assert (r["total"], r["local"], r["empate"], r["visitante"]) == (3, 2, 0, 1)
    assert r["marcadores"][0] == {"goles_local": 2, "goles_visitante": 1, "cantidad": 2}
    assert r["mi_prediccion"]["goles_visitante"] == 3 and r["resultado_real"] is None
    anonimo = cliente.get(f"{BASE}/partidos/P-002/predicciones").json()
    assert anonimo["mi_prediccion"] is None


def test_partido_finalizado_se_puntua_y_arma_la_tabla(cliente, adaptadores):
    adaptadores.neo4j.estado("P-003", "Programado")
    jugadas = {"pleno": (0, 1), "ganador": (1, 3), "empate": (1, 1), "erra": (2, 0)}
    sesiones = {}
    for alias, (gl, gv) in jugadas.items():
        sesiones[alias] = _login(cliente, f"h_{alias}", "URU" if alias != "erra" else "ESP")[0]
        assert _pronosticar(cliente, sesiones[alias], "P-003", gl, gv).status_code == 200

    # Antes del final: todos figuran con 0 puntos.
    tabla = cliente.get(f"{BASE}/posiciones").json()
    assert tabla["total_participantes"] == 4 and all(f["puntos"] == 0 for f in tabla["filas"])

    # El control de la demo cierra el partido en Neo4j (ESP 0 - 1 URU).
    r = cliente.put(f"{BASE}/partidos/P-003/estado", headers=sesiones["pleno"], json={"estado": "Finalizado"})
    assert r.status_code == 200 and r.json()["estado"] == "Finalizado"
    tabla = cliente.get(f"{BASE}/posiciones", headers=sesiones["ganador"]).json()
    puntos = {f["alias"]: (f["posicion"], f["puntos"], f["exactos"]) for f in tabla["filas"]}
    assert puntos == {"h_pleno": (1, 3, 1), "h_ganador": (2, 1, 0), "h_empate": (3, 0, 0), "h_erra": (3, 0, 0)}
    assert tabla["mi_fila"]["alias"] == "h_ganador" and tabla["puntos_exacto"] == 3

    # Tabla por hinchada.
    hinchada = cliente.get(f"{BASE}/posiciones?equipo=ESP").json()
    assert [f["alias"] for f in hinchada["filas"]] == ["h_erra"] and hinchada["filas"][0]["posicion"] == 1

    # Una vez puntuado no se puede cambiar y la liquidación no se repite.
    assert _pronosticar(cliente, sesiones["erra"], "P-003", 0, 1).status_code == 409
    assert adaptadores.mongodb.liquidar_partido("P-003", 0, 1, 3, 1) == 0
    resumen = cliente.get(f"{BASE}/partidos/P-003/predicciones", headers=sesiones["pleno"]).json()
    assert not resumen["abierta"] and resumen["resultado_real"] == {"goles_local": 0, "goles_visitante": 1}
    assert resumen["mi_prediccion"]["acierto"] == "exacto"


def test_tabla_se_sirve_aunque_neo4j_no_responda(cliente, adaptadores):
    adaptadores.neo4j.estado("P-003", "Programado")
    h, _ = _login(cliente, "hincha_uno")
    _pronosticar(cliente, h, "P-003", 0, 1)
    adaptadores.neo4j.estado("P-003", "Finalizado")
    adaptadores.neo4j.falla = DependenciaNoDisponible("neo4j")
    r = cliente.get(f"{BASE}/posiciones")
    assert r.status_code == 200 and r.json()["pendientes"] == ["P-003"]


def test_posiciones_valida_filtro(cliente, adaptadores):
    assert cliente.get(f"{BASE}/posiciones?equipo=arg").status_code == 400
    assert cliente.get(f"{BASE}/posiciones?limit=0").status_code == 400
    assert sin_llamadas(adaptadores)


def test_marcador_cuenta_goles_por_seleccion_del_jugador():
    eventos = [{"tipo": "Gol", "jugador": {"id_jugador": "ARG-10"}}, {"tipo": "gol", "jugador": {"id_jugador": "ESP-7"}},
               {"tipo": "Gol", "jugador": {"id_jugador": "ARG-9"}}, {"tipo": "Tarjeta", "jugador": {"id_jugador": "ARG-4"}},
               {"tipo": "Gol", "jugador": None}]
    assert marcador(eventos, "ARG", "ESP") == (2, 1)


def test_prode_fuera_del_contrato_openapi(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert not any("prediccion" in p or "posiciones" in p for p in rutas)

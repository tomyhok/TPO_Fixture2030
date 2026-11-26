"""Simulación en tiempo real al iniciar un partido desde el portal, con dobles.

Con `simulacion_duracion_s=0` el partido completo se juega al instante en el hilo del
simulador; las pruebas esperan a que termine y revisan lo que quedó en cada base.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.dependencias import Adaptadores
from app.main import crear_app
from app.services.prode_service import marcador

BASE = "/portal/api"


def _cliente(adaptadores: Adaptadores, duracion_s: float) -> TestClient:
    settings = Settings(_env_file=None, simulacion_duracion_s=duracion_s)
    return TestClient(crear_app(adaptadores=adaptadores, settings=settings), raise_server_exceptions=False)


@pytest.fixture
def instantaneo(adaptadores: Adaptadores) -> Iterator[TestClient]:
    with _cliente(adaptadores, 0) as c:
        yield c


def _login(cliente, alias="hincha_sim"):
    r = cliente.post(f"{BASE}/sesiones", json={"alias": alias, "equipo_favorito": "URU"})
    return {"X-Sesion-ID": r.json()["id_sesion"]}


def _simulador(cliente):
    return cliente.app.state.servicios.simulador


def test_iniciar_partido_simula_y_finaliza(instantaneo, adaptadores):
    h = _login(instantaneo)
    assert instantaneo.put(f"{BASE}/partidos/P-002/prediccion", headers=h,
                           json={"goles_local": 1, "goles_visitante": 1}).status_code == 200
    r = instantaneo.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"})
    assert r.status_code == 200 and r.json()["inicio"]
    assert _simulador(instantaneo).esperar("P-002", 5)

    partido = next(p for p in adaptadores.neo4j.partidos if p["codigo_partido"] == "P-002")
    assert partido["estado"] == "Finalizado"

    # Neo4j: eventos del modelo del Hito 5, de jugadores de las dos selecciones.
    eventos = adaptadores.neo4j.EVENTOS["P-002"]
    assert all(e["tipo"] in {"Gol", "Tarjeta Amarilla", "Tarjeta Roja"} for e in eventos)
    assert all(e["jugador"]["id_jugador"][:3] in {"URU", "ARG"} for e in eventos)
    assert all(e["id_evento"].startswith("SIM-P-002-") for e in eventos)

    # Redis: el reloj terminó después del minuto 90.
    reloj = adaptadores.redis.relojes["P-002"]
    assert not reloj["en_curso"] and reloj["minuto"] == 90 + reloj["adicion"] and 1 <= reloj["adicion"] <= 5

    # InfluxDB: un punto por minuto (incluido el 0) y por selección, con tiros >= goles.
    assert len(adaptadores.influxdb.lineas) == 2 * (reloj["minuto"] + 1)
    assert all(l.startswith("estadisticas_partido,partido_id=P-002,equipo_id=") for l in adaptadores.influxdb.lineas)

    # Cassandra: el relator abre y cierra el partido con el marcador de Neo4j.
    textos = [c["texto"] for c in adaptadores.cassandra.publicados if c["id_usuario"] == "U-0000"]
    gl, gv = marcador(eventos, "URU", "ARG")
    assert textos[-1].startswith("¡Arranca el partido!") and textos[0] == f"¡Terminó el partido! Uruguay {gl} - {gv} Argentina."
    assert sum(t.startswith("⚽") for t in textos) == gl + gv

    # El prode puntúa con ese resultado en la próxima consulta.
    resumen = instantaneo.get(f"{BASE}/partidos/P-002/predicciones", headers=h).json()
    assert resumen["resultado_real"] == {"goles_local": gl, "goles_visitante": gv}
    assert resumen["mi_prediccion"]["puntos"] in (0, 1, 3)


def test_finalizar_a_mano_detiene_la_simulacion(adaptadores):
    with _cliente(adaptadores, 60) as cliente:
        h = _login(cliente)
        assert cliente.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"}).status_code == 200
        assert _simulador(cliente).en_curso("P-002")
        vivo = cliente.get(f"{BASE}/partidos/P-002/vivo").json()
        assert vivo["reloj"]["en_curso"]
        assert cliente.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "Finalizado"}).status_code == 200
        assert _simulador(cliente).esperar("P-002", 5)
        assert not cliente.get(f"{BASE}/partidos/P-002/vivo").json()["reloj"]["en_curso"]


def test_sin_planteles_no_arranca(instantaneo, adaptadores):
    adaptadores.neo4j.jugadores = {}
    h = _login(instantaneo)
    r = instantaneo.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"})
    assert r.status_code == 409
    assert next(p for p in adaptadores.neo4j.partidos if p["codigo_partido"] == "P-002")["estado"] == "Programado"


def test_una_base_caida_no_corta_la_simulacion(instantaneo, adaptadores):
    from app.core.errores import DependenciaNoDisponible

    adaptadores.cassandra.falla = DependenciaNoDisponible("cassandra")
    adaptadores.influxdb.falla = DependenciaNoDisponible("influxdb")
    h = _login(instantaneo)
    assert instantaneo.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"}).status_code == 200
    assert _simulador(instantaneo).esperar("P-002", 5)
    assert next(p for p in adaptadores.neo4j.partidos if p["codigo_partido"] == "P-002")["estado"] == "Finalizado"
    assert not adaptadores.redis.relojes["P-002"]["en_curso"]


def test_hinchada_simulada_comenta_en_cassandra(instantaneo, adaptadores):
    h = _login(instantaneo)
    assert instantaneo.put(f"{BASE}/partidos/P-002/estado", headers=h, json={"estado": "En Juego"}).status_code == 200
    assert _simulador(instantaneo).esperar("P-002", 5)
    hinchas = [c for c in adaptadores.cassandra.publicados if c["id_usuario"] not in ("U-0000",)]
    # ~0,8 comentarios por minuto más reacciones, entretiempo y final.
    assert len(hinchas) >= 40
    assert all(9001 <= int(c["id_usuario"][2:]) <= 9024 and c["equipo_apoyado"] in {"URU", "ARG"} for c in hinchas)
    # Cada hincha alienta a una sola selección en el partido y la tribuna está repartida.
    equipo_de = {}
    for c in hinchas:
        assert equipo_de.setdefault(c["id_usuario"], c["equipo_apoyado"]) == c["equipo_apoyado"]
    assert set(equipo_de.values()) == {"URU", "ARG"}
    # Cada gol tiene al menos dos festejos de hinchas de quien lo hizo, en ese minuto.
    for gol in (e for e in adaptadores.neo4j.EVENTOS["P-002"] if e["tipo"] == "Gol"):
        iso = gol["jugador"]["id_jugador"][:3]
        festejos = [c for c in hinchas if c["minuto_partido"] == gol["minuto"] and c["equipo_apoyado"] == iso]
        assert len(festejos) >= 2
    assert all(1 <= len(c["texto"]) <= 280 for c in hinchas)


def test_todas_las_frases_se_pueden_completar():
    from app.services.simulador_service import FRASES

    for tipo, frases in FRASES.items():
        for frase in frases:
            frase.format(eq="Uruguay", rival="Argentina", jugador="Nueve", sede="Estadio Centenario",
                         min="45'", marcador="1-0")

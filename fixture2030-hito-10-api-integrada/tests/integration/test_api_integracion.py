"""Integración (5.12): cada caso de uso contra su fuente real.

Cubre por módulo: request válida, recurso inexistente, respuesta vacía válida,
límites/paginación/ventanas, sesión ausente o expirada y escritura repetida.
Cada respuesta se contrasta con el contrato OpenAPI (`documentado`).
"""

import time
import uuid
from datetime import datetime

import pytest

from tests.integration.conftest import documentado

pytestmark = pytest.mark.integracion


def clave() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


# ------------------------------------------------------------------ MongoDB
class TestMongoDB:
    def test_ficha_de_seleccion(self, cliente):
        r = cliente.get("/equipos/ARG")
        documentado(r, "get", "/equipos/{codigo_iso}")
        assert r.status_code == 200
        assert r.json()["nombre"] == "Argentina" and r.json()["confederacion"] == "CONMEBOL"

    def test_seleccion_inexistente(self, cliente):
        r = cliente.get("/equipos/XYZ")
        documentado(r, "get", "/equipos/{codigo_iso}")
        assert r.status_code == 404

    def test_paginacion_ordenada_por_ranking(self, cliente):
        paginas = [cliente.get(f"/equipos?size=10&page={p}").json() for p in range(1, 8)]
        assert all(p["total"] == 64 for p in paginas)
        assert [len(p["items"]) for p in paginas] == [10] * 6 + [4]
        rankings = [e["ranking_fifa"] for p in paginas for e in p["items"]]
        assert rankings == sorted(rankings)
        codigos = [e["codigo_iso"] for p in paginas for e in p["items"]]
        assert len(set(codigos)) == 64  # sin repetidos entre páginas

    def test_pagina_fuera_de_rango_es_vacia(self, cliente):
        r = cliente.get("/equipos?size=50&page=3")
        assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 64

    def test_plantel_filtrado_por_posicion(self, cliente):
        r = cliente.get("/equipos/ARG/jugadores?posicion=ARQ")
        documentado(r, "get", "/equipos/{codigo_iso}/jugadores")
        assert r.status_code == 200 and r.json()["total"] >= 1
        assert {j["posicion"] for j in r.json()["items"]} == {"ARQ"}

    def test_jugador(self, cliente):
        r = cliente.get("/jugadores/ARG-10")
        documentado(r, "get", "/jugadores/{id_jugador}")
        assert r.json()["codigo_equipo"] == "ARG" and r.json()["dorsal"] == 10


# -------------------------------------------------------------------- Neo4j
class TestNeo4j:
    def test_ficha_con_cache_miss_y_hit(self, cliente, redis_directo):
        redis_directo.delete("cache:partido:P-001")
        primera = cliente.get("/partidos/P-001")
        documentado(primera, "get", "/partidos/{codigo_partido}")
        assert primera.status_code == 200 and primera.headers["X-Cache"] == "MISS"
        assert primera.json()["local"]["codigo_iso"] == "ARG"
        assert primera.json()["sede"]["codigo_sede"] == "MON"
        assert 0 < redis_directo.ttl("cache:partido:P-001") <= 300
        segunda = cliente.get("/partidos/P-001")
        assert segunda.headers["X-Cache"] == "HIT" and segunda.json() == primera.json()

    def test_partido_inexistente(self, cliente):
        r = cliente.get("/partidos/P-999")
        documentado(r, "get", "/partidos/{codigo_partido}")
        assert r.status_code == 404

    def test_eventos_inexistente_vs_sin_eventos(self, cliente):
        con = cliente.get("/partidos/P-001/eventos")
        documentado(con, "get", "/partidos/{codigo_partido}/eventos")
        assert con.json()["eventos"][0]["id_evento"] == "EV-001"
        assert con.json()["eventos"][0]["jugador"]["id_jugador"] == "ARG-10"
        sin = cliente.get("/partidos/P-002/eventos")
        assert sin.status_code == 200 and sin.json()["eventos"] == []
        assert cliente.get("/partidos/P-999/eventos").status_code == 404

    def test_rivales_con_limite(self, cliente):
        r = cliente.get("/equipos/ARG/rivales")
        documentado(r, "get", "/equipos/{codigo_iso}/rivales")
        assert {x["codigo_iso"] for x in r.json()["rivales"]} == {"ESP", "URU"}
        assert len(cliente.get("/equipos/ARG/rivales?limit=1").json()["rivales"]) == 1


# ---------------------------------------------------------------- Cassandra
class TestCassandra:
    VENTANA = "203006152015"  # 5 comentarios de P-001 en la muestra del Hito 6

    def test_muro_paginado_con_cursor(self, cliente):
        p1 = cliente.get(f"/partidos/P-001/comentarios?ventana={self.VENTANA}&limit=3")
        documentado(p1, "get", "/partidos/{codigo_partido}/comentarios")
        assert len(p1.json()["items"]) == 3 and p1.json()["cursor_siguiente"]
        p2 = cliente.get(
            f"/partidos/P-001/comentarios?ventana={self.VENTANA}&limit=3&cursor={p1.json()['cursor_siguiente']}"
        )
        assert len(p2.json()["items"]) == 2 and p2.json()["cursor_siguiente"] is None
        todos = p1.json()["items"] + p2.json()["items"]
        assert len({c["id_comentario"] for c in todos}) == 5
        instantes = [datetime.fromisoformat(c["creado_en"]) for c in todos]
        assert instantes == sorted(instantes, reverse=True)

    def test_ventana_sin_comentarios(self, cliente):
        r = cliente.get("/partidos/P-001/comentarios?ventana=203001010000")
        assert r.status_code == 200 and r.json()["items"] == []

    def test_publicar_y_repetir_no_duplica(self, cliente):
        cuerpo = {"id_usuario": "U-1001", "usuario_alias": "hincha_albiceleste", "equipo_apoyado": "ARG",
                  "texto": f"Prueba de integración {uuid.uuid4()}", "idioma": "es", "minuto_partido": 67}
        headers = clave()
        creado = cliente.post("/partidos/P-001/comentarios", json=cuerpo, headers=headers)
        documentado(creado, "post", "/partidos/{codigo_partido}/comentarios")
        assert creado.status_code == 201
        repetido = cliente.post("/partidos/P-001/comentarios", json=cuerpo, headers=headers)
        documentado(repetido, "post", "/partidos/{codigo_partido}/comentarios")
        assert repetido.status_code == 200 and repetido.headers["Idempotent-Replayed"] == "true"
        assert repetido.json()["id_comentario"] == creado.json()["id_comentario"]

        muro = cliente.get(creado.headers["Location"] + "&limit=100").json()["items"]
        assert [c["texto"] for c in muro].count(cuerpo["texto"]) == 1

        otro = cliente.post("/partidos/P-001/comentarios", json={**cuerpo, "minuto_partido": 68}, headers=headers)
        documentado(otro, "post", "/partidos/{codigo_partido}/comentarios")
        assert otro.status_code == 409

    def test_publicar_en_partido_inexistente(self, cliente):
        cuerpo = {"id_usuario": "U-1001", "usuario_alias": "hincha", "equipo_apoyado": "ARG",
                  "texto": "x", "idioma": "es", "minuto_partido": 1}
        r = cliente.post("/partidos/P-999/comentarios", json=cuerpo, headers=clave())
        documentado(r, "post", "/partidos/{codigo_partido}/comentarios")
        assert r.status_code == 404


# -------------------------------------------------------------------- Redis
class TestRedis:
    def test_sesion_vigente_no_expone_datos_internos(self, cliente, redis_directo):
        redis_directo.hset("sesion:S-8001", mapping={
            "id_sesion": "S-8001", "usuario_id": "U-8001", "rol": "fan", "estado": "activa",
            "dispositivo": "web", "paginas_vistas": 3})
        redis_directo.expire("sesion:S-8001", 60)
        r = cliente.get("/sesiones/S-8001")
        documentado(r, "get", "/sesiones/{id_sesion}")
        assert r.status_code == 200
        assert set(r.json()) == {"id_sesion", "usuario_id", "rol", "estado", "ttl_restante_s"}
        assert 0 < r.json()["ttl_restante_s"] <= 60

    def test_sesion_expirada(self, cliente, redis_directo):
        redis_directo.hset("sesion:S-8002", mapping={"usuario_id": "U-8002", "rol": "fan", "estado": "activa"})
        redis_directo.expire("sesion:S-8002", 1)
        assert cliente.get("/sesiones/S-8002").status_code == 200
        time.sleep(1.5)
        r = cliente.get("/sesiones/S-8002")
        documentado(r, "get", "/sesiones/{id_sesion}")
        assert r.status_code == 404 and r.json()["error"]["codigo"] == "SESION_NO_VIGENTE"

    def test_cerrar_sesion_idempotente(self, cliente, redis_directo):
        redis_directo.hset("sesion:S-8003", mapping={"usuario_id": "U-8003", "rol": "fan", "estado": "activa"})
        redis_directo.expire("sesion:S-8003", 60)
        primera = cliente.delete("/sesiones/S-8003")
        documentado(primera, "delete", "/sesiones/{id_sesion}")
        assert primera.status_code == 204
        assert cliente.delete("/sesiones/S-8003").status_code == 204
        assert redis_directo.exists("sesion:S-8003") == 0
        assert cliente.get("/sesiones/S-8003").status_code == 404


# ----------------------------------------------------------------- InfluxDB
class TestInfluxDB:
    RUTA = "/partidos/P-001/estadisticas"

    def test_ventana_agregada_por_equipo(self, cliente):
        r = cliente.get(f"{self.RUTA}?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T22:00:00Z&resolucion=5m")
        documentado(r, "get", "/partidos/{codigo_partido}/estadisticas")
        series = {s["equipo"]: s["puntos"] for s in r.json()["series"]}
        assert set(series) == {"ARG", "ESP"}
        assert len(series["ARG"]) == len(series["ESP"]) == 24  # 2 h / 5 min
        # La posesión de los dos equipos suma 100 en cada ventana.
        for a, e in zip(series["ARG"], series["ESP"], strict=True):
            assert abs(a["posesion_pct_prom"] + e["posesion_pct_prom"] - 100) < 0.05
        # Los contadores acumulados nunca bajan.
        pases = [p["pases_completados_max"] for p in series["ARG"]]
        assert pases == sorted(pases)

    def test_limite_de_puntos(self, cliente):
        r = cliente.get(f"{self.RUTA}?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T23:00:00Z&resolucion=10s&equipo=ARG")
        assert r.status_code == 200
        assert [s["equipo"] for s in r.json()["series"]] == ["ARG"]
        assert len(r.json()["series"][0]["puntos"]) <= 1081

    def test_ventana_sin_puntos(self, cliente):
        r = cliente.get(f"{self.RUTA}?desde=2031-01-01T00:00:00Z&hasta=2031-01-01T01:00:00Z")
        documentado(r, "get", "/partidos/{codigo_partido}/estadisticas")
        assert r.status_code == 200 and r.json()["series"] == []

    def test_intervalo_invertido(self, cliente):
        r = cliente.get(f"{self.RUTA}?desde=2030-06-10T22:00:00Z&hasta=2030-06-10T20:00:00Z")
        documentado(r, "get", "/partidos/{codigo_partido}/estadisticas")
        assert r.status_code == 400


# --------------------------------------------------------------------- IRIS
class TestIRIS:
    def test_acta_y_acta_inexistente(self, cliente, actas_reiniciadas):
        r = cliente.get("/partidos-oficiales/P-001")
        documentado(r, "get", "/partidos-oficiales/{codigo_partido}")
        assert r.json()["estado"] == "En Juego" and r.json()["eventos"][0]["minuto"] == 23
        assert "DNI" not in r.text and "dni" not in r.json()["arbitro"]
        ausente = cliente.get("/partidos-oficiales/P-999")
        documentado(ausente, "get", "/partidos-oficiales/{codigo_partido}")
        assert ausente.status_code == 404

    def test_ciclo_de_vida_del_acta(self, cliente, actas_reiniciadas):
        base = "/partidos-oficiales/P-002"

        salto = cliente.patch(f"{base}/estado", json={"estado": "Finalizado"})
        documentado(salto, "patch", "/partidos-oficiales/{codigo_partido}/estado")
        assert salto.status_code == 409  # Programado -> Finalizado no está permitido

        inicio = cliente.patch(f"{base}/estado", json={"estado": "En Juego"})
        assert inicio.status_code == 200 and inicio.json()["cambiado"] is True
        repetido = cliente.patch(f"{base}/estado", json={"estado": "En Juego"})
        assert repetido.status_code == 200 and repetido.json()["cambiado"] is False

        headers = clave()
        evento = {"minuto": 12, "tipo": "Gol", "descripcion": "Gol de URU-9"}
        creado = cliente.post(f"{base}/eventos", json=evento, headers=headers)
        documentado(creado, "post", "/partidos-oficiales/{codigo_partido}/eventos")
        assert creado.status_code == 201
        reintento = cliente.post(f"{base}/eventos", json=evento, headers=headers)
        assert reintento.status_code == 200 and reintento.headers["Idempotent-Replayed"] == "true"

        assert cliente.patch(f"{base}/estado", json={"estado": "Finalizado"}).status_code == 200
        tarde = cliente.post(f"{base}/eventos", json={"minuto": 95, "tipo": "Gol"}, headers=clave())
        documentado(tarde, "post", "/partidos-oficiales/{codigo_partido}/eventos")
        assert tarde.status_code == 409 and tarde.json()["error"]["codigo"] == "CONFLICTO_ESTADO"
        assert cliente.patch(f"{base}/estado", json={"estado": "En Juego"}).status_code == 409

        acta = cliente.get(base).json()
        assert acta["estado"] == "Finalizado"
        assert [e["minuto"] for e in acta["eventos"]] == [12]  # ni duplicado ni el evento tardío


# -------------------------------------------------------------------- Salud
def test_health_todas_las_fuentes(cliente):
    r = cliente.get("/health")
    documentado(r, "get", "/health")
    assert r.status_code == 200
    assert {d["nombre"]: d["estado"] for d in r.json()["dependencias"]} == {
        n: "ok" for n in ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")}

"""Casos de uso con dobles: éxito, ausencia, vacío válido y conflicto por módulo."""

import uuid


# --------------------------------------------------------------- MongoDB
def test_cu01_ficha_seleccion(cliente):
    r = cliente.get("/equipos/ARG")
    assert r.status_code == 200
    assert r.json()["codigo_iso"] == "ARG"
    assert "_id" not in r.json()


def test_cu01_seleccion_inexistente(cliente):
    r = cliente.get("/equipos/XYZ")
    assert r.status_code == 404
    assert r.json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_cu02_lista_paginada_y_vacia(cliente):
    r = cliente.get("/equipos?confederacion=UEFA&size=1")
    assert r.status_code == 200
    assert r.json() == {"items": [r.json()["items"][0]], "page": 1, "size": 1, "total": 1}
    vacia = cliente.get("/equipos?confederacion=OFC")
    assert vacia.status_code == 200
    assert vacia.json()["items"] == [] and vacia.json()["total"] == 0


def test_cu03_plantel_distingue_inexistente_de_vacio(cliente):
    assert cliente.get("/equipos/ARG/jugadores").json()["total"] == 1
    vacio = cliente.get("/equipos/ARG/jugadores?posicion=ARQ")
    assert vacio.status_code == 200 and vacio.json()["items"] == []
    assert cliente.get("/equipos/XYZ/jugadores").status_code == 404


def test_cu04_jugador(cliente):
    assert cliente.get("/jugadores/ARG-10").json()["codigo_equipo"] == "ARG"
    assert cliente.get("/jugadores/ARG-99").status_code == 404


# ----------------------------------------------------------------- Neo4j
def test_cu05_cache_miss_y_luego_hit(cliente, adaptadores):
    primera = cliente.get("/partidos/P-001")
    assert primera.status_code == 200 and primera.headers["X-Cache"] == "MISS"
    segunda = cliente.get("/partidos/P-001")
    assert segunda.headers["X-Cache"] == "HIT"
    assert segunda.json() == primera.json()
    assert adaptadores.neo4j.llamadas.count("ficha_partido") == 1


def test_cu05_cache_con_formato_viejo_se_reemplaza(cliente, adaptadores):
    adaptadores.redis.cache["P-001"] = '{"codigo_partido":"P-001","local":"ARG"}'  # formato del Hito 7
    r = cliente.get("/partidos/P-001")
    assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"


def test_cu05_inexistente_no_se_cachea(cliente, adaptadores):
    assert cliente.get("/partidos/P-999").status_code == 404
    assert "P-999" not in adaptadores.redis.cache


def test_cu06_partido_inexistente_vs_sin_eventos(cliente):
    assert cliente.get("/partidos/P-999/eventos").status_code == 404
    vacio = cliente.get("/partidos/P-002/eventos")
    assert vacio.status_code == 200 and vacio.json()["eventos"] == []
    con_eventos = cliente.get("/partidos/P-001/eventos").json()
    assert con_eventos["eventos"][0]["jugador"]["id_jugador"] == "ARG-10"


def test_cu07_rivales(cliente):
    assert cliente.get("/equipos/ARG/rivales").json()["rivales"][0]["codigo_iso"] == "ESP"
    assert cliente.get("/equipos/XYZ/rivales").status_code == 404


# ------------------------------------------------------------- Cassandra
def test_cu08_muro_y_ventana_vacia(cliente):
    r = cliente.get("/partidos/P-001/comentarios?ventana=203006152016")
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    assert r.json()["cursor_siguiente"] is None
    vacia = cliente.get("/partidos/P-001/comentarios?ventana=203006152030")
    assert vacia.status_code == 200 and vacia.json()["items"] == []


def test_cu09_publicar_calcula_particion(cliente, adaptadores):
    cuerpo = {"id_usuario": "U-1001", "usuario_alias": "hincha", "equipo_apoyado": "ARG",
              "texto": "Vamos", "idioma": "es", "minuto_partido": 10}
    r = cliente.post("/partidos/P-001/comentarios", json=cuerpo, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201
    escrito = adaptadores.cassandra.publicados[0]
    assert 0 <= escrito["shard"] < 4 and len(escrito["ventana"]) == 12 and len(escrito["periodo"]) == 6
    assert escrito["estado_moderacion"] == "publicado"
    assert r.headers["Location"] == f"/partidos/P-001/comentarios?ventana={escrito['ventana']}"
    assert "shard" not in r.json()


def test_cu09_partido_inexistente_no_escribe(cliente, adaptadores):
    cuerpo = {"id_usuario": "U-1001", "usuario_alias": "hincha", "equipo_apoyado": "ARG",
              "texto": "Vamos", "idioma": "es", "minuto_partido": 10}
    r = cliente.post("/partidos/P-999/comentarios", json=cuerpo, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 404
    assert adaptadores.cassandra.publicados == []
    assert adaptadores.redis.idem == {}  # la clave se liberó


# ----------------------------------------------------------------- Redis
def test_cu10_sesion_vigente_y_no_vigente(cliente):
    r = cliente.get("/sesiones/S-0001")
    assert r.status_code == 200
    assert set(r.json()) == {"id_sesion", "usuario_id", "rol", "estado", "ttl_restante_s"}
    ausente = cliente.get("/sesiones/S-9999")
    assert ausente.status_code == 404
    assert ausente.json()["error"]["codigo"] == "SESION_NO_VIGENTE"


def test_cu11_cerrar_sesion_es_idempotente(cliente):
    assert cliente.delete("/sesiones/S-0001").status_code == 204
    assert cliente.delete("/sesiones/S-0001").status_code == 204
    assert cliente.get("/sesiones/S-0001").status_code == 404


# -------------------------------------------------------------- InfluxDB
def test_cu12_series_y_tope_de_puntos(cliente, adaptadores):
    r = cliente.get("/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T23:00:00Z&resolucion=10s")
    assert r.status_code == 200
    assert [s["equipo"] for s in r.json()["series"]] == ["ARG", "ESP"]
    assert adaptadores.influxdb.ultimo_tope == (3 * 3600 // 10 + 1) * 2
    uno = cliente.get("/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T21:00:00Z&equipo=ARG")
    assert [s["equipo"] for s in uno.json()["series"]] == ["ARG"]


def test_cu12_ventana_sin_puntos_es_200_vacio(cliente):
    r = cliente.get("/partidos/P-002/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T21:00:00Z")
    assert r.status_code == 200 and r.json()["series"] == []


# ------------------------------------------------------------------ IRIS
def test_cu13_acta(cliente):
    assert cliente.get("/partidos-oficiales/P-001").json()["arbitro"]["apellido"] == "Tello"
    assert cliente.get("/partidos-oficiales/P-999").status_code == 404


def test_cu14_transiciones(cliente):
    mismo = cliente.patch("/partidos-oficiales/P-001/estado", json={"estado": "En Juego"})
    assert mismo.status_code == 200 and mismo.json()["cambiado"] is False
    invalida = cliente.patch("/partidos-oficiales/P-001/estado", json={"estado": "Programado"})
    assert invalida.status_code == 409
    assert invalida.json()["error"]["detalles"] == [{"estado_actual": "En Juego", "estado_pedido": "Programado"}]
    valida = cliente.patch("/partidos-oficiales/P-001/estado", json={"estado": "Finalizado"})
    assert valida.status_code == 200 and valida.json()["acta"]["estado"] == "Finalizado"
    assert cliente.patch("/partidos-oficiales/P-999/estado", json={"estado": "En Juego"}).status_code == 404


def test_cu15_evento_y_partido_finalizado(cliente):
    ok = cliente.post("/partidos-oficiales/P-001/eventos", json={"minuto": 50, "tipo": "Gol"},
                      headers={"Idempotency-Key": str(uuid.uuid4())})
    assert ok.status_code == 201 and ok.json()["acta"]["eventos"][-1]["minuto"] == 50
    finalizado = cliente.post("/partidos-oficiales/P-003/eventos", json={"minuto": 50, "tipo": "Gol"},
                              headers={"Idempotency-Key": str(uuid.uuid4())})
    assert finalizado.status_code == 409
    assert finalizado.json()["error"]["codigo"] == "CONFLICTO_ESTADO"


# ----------------------------------------------------------------- Salud
def test_cu16_health(cliente, adaptadores):
    r = cliente.get("/health")
    assert r.status_code == 200 and r.json()["estado"] == "ok"
    assert {d["nombre"] for d in r.json()["dependencias"]} == {
        "mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"}

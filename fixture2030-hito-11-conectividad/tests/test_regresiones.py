"""Casos de regresión hallados en la revisión del Hito 11; no requieren bases."""

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluar_conectividad as cli
from conectividad import api
from conectividad.config import Config
from conectividad.productos import cassandra, influxdb, iris, mongodb, neo4j, redis_kv
from conectividad.red import RespuestaHTTP
from conectividad.registro import FAIL, OK, SKIP, WARN, Redactor, Registro, Resultado, matriz


def cfg(**valores):
    return Config({"HITO10_ENV": "/no/existe", **valores})


def registro():
    return Registro(Redactor([]), salida=io.StringIO())


def resultado(producto, capa, estado, **datos):
    return Resultado(producto, capa, "prueba", estado, "detalle", "destino", "fecha", 1, datos=datos)


@pytest.mark.parametrize("estado,datos", [(FAIL, {}), (WARN, {"degrada": True})])
def test_matriz_incluye_resultados_api_compartidos(estado, datos):
    reg = registro()
    reg.resultados = [resultado("mongodb", "lectura", OK), resultado("redis", "lectura", OK),
                      resultado("api", "api", estado, dependencias=["mongodb"], **datos)]
    filas = matriz(reg, ["mongodb", "redis"])
    assert filas[0]["estado"] == "degradado"
    assert filas[0]["api"] == estado
    assert filas[1]["estado"] == "disponible"


def test_error_de_configuracion_no_desaparece_del_json_ni_del_codigo_de_salida(monkeypatch, tmp_path):
    destino = tmp_path / "resultado.json"
    monkeypatch.setattr(cli, "Config", lambda: cfg(REDIS_PORT="invalido"))
    monkeypatch.setattr(sys, "argv", ["evaluar", "--modo", "tcp", "--producto", "redis", "--estricto",
                                     "--json", str(destino)])
    assert cli.main() == 1
    data = json.loads(destino.read_text(encoding="utf-8"))
    assert data["meta"]["conteo"][FAIL] == 1
    assert data["matriz"][0]["estado"] == "desconocido"
    assert data["resultados"][0]["hipotesis"] and data["resultados"][0]["siguiente_paso"]


def test_capas_desconocidas_no_generan_una_corrida_vacia_exitosa(monkeypatch):
    monkeypatch.setattr(cli, "Config", cfg)
    monkeypatch.setattr(sys, "argv", ["evaluar", "--capas", "lectrua"])
    assert cli.main() == 2


def test_api_inaccesible_degrada_las_fuentes_nativas_disponibles(monkeypatch):
    def sin_api(*args, **kwargs):
        raise ConnectionRefusedError()
    monkeypatch.setattr(api, "http", sin_api)
    reg = registro()
    reg.resultados.append(resultado("mongodb", "lectura", OK))
    api.evaluar(cfg(), reg, ["mongodb"])
    assert matriz(reg, ["mongodb"])[0]["estado"] == "degradado"


def test_readiness_parcial_afecta_solo_a_la_fuente_informada(monkeypatch):
    cuerpo = {"listo": True, "estado": "degraded", "no_disponibles": ["redis"]}
    monkeypatch.setattr(api, "CASOS", [api.Caso("readiness", "/health/ready", ["mongodb", "redis"], {api.EXITO})])
    monkeypatch.setattr(api, "http", lambda *a, **kw: RespuestaHTTP(200, {}, json.dumps(cuerpo).encode(), 1))
    reg = registro()
    reg.resultados = [resultado(p, "lectura", OK) for p in ("mongodb", "redis")]
    api.evaluar(cfg(), reg, ["mongodb", "redis"])
    filas = matriz(reg, ["mongodb", "redis"])
    assert [f["estado"] for f in filas] == ["disponible", "degradado"]


@pytest.fixture
def driver_cassandra(monkeypatch):
    import cassandra.cluster
    tabla = SimpleNamespace(partition_key=[SimpleNamespace(name=n) for n in ("id_partido", "ventana", "shard")],
                            clustering_key=[SimpleNamespace(name="id_comentario")])
    ks = SimpleNamespace(tables={"comentarios_por_partido": tabla}, replication_strategy=MagicMock())
    cluster = MagicMock()
    cluster.metadata.keyspaces = {"fixture2030": ks}
    sesion = cluster.connect.return_value
    sesion.execute.return_value = []
    monkeypatch.setattr(cassandra.cluster, "Cluster", lambda **kw: cluster)
    return cluster, sesion


def test_cassandra_lectura_aislada_inicializa_sesion(driver_cassandra):
    cluster, sesion = driver_cassandra
    reg = registro()
    cassandra.evaluar(cfg(), reg, {"lectura"}, False)
    cluster.connect.assert_called_once_with()
    assert len(reg.resultados) == 1 and reg.resultados[0].estado == WARN
    assert sesion.prepare.called and sesion.execute.call_count == 4
    cluster.shutdown.assert_called_once()


def test_cassandra_contexto_aislado_no_declara_inexistencia_sin_conectar(driver_cassandra):
    cluster, _ = driver_cassandra
    reg = registro()
    cassandra.evaluar(cfg(), reg, {"contexto"}, False)
    cluster.connect.assert_called_once()
    assert reg.resultados[0].estado == OK


def test_cassandra_sondas_no_atribuyen_falla_de_keyspace_a_particion(driver_cassandra):
    cluster, sesion = driver_cassandra
    cluster.metadata.keyspaces = {}
    reg = registro()
    cassandra.evaluar(cfg(), reg, {"sonda"}, True)
    assert reg.resultados[0].estado == SKIP
    assert not sesion.execute.called


def test_cassandra_clasifica_corte_de_conexion_y_auth_sin_importerror():
    from cassandra import AuthenticationFailed
    from cassandra.cluster import NoHostAvailable
    assert cassandra._clasificar(ConnectionError("corte"), "protocolo").estado == FAIL
    paso = cassandra._clasificar(NoHostAvailable("login", {"127.0.0.1": AuthenticationFailed("no")}), "autenticacion")
    assert paso.estado == FAIL and "credencial" in paso.detalle


def test_cassandra_sonda_verifica_causa_del_invalidrequest(driver_cassandra):
    from cassandra import InvalidRequest
    _, sesion = driver_cassandra
    sesion.execute.side_effect = InvalidRequest("keyspace fixture2030 does not exist")
    reg = registro()
    cassandra.evaluar(cfg(), reg, {"sonda"}, True)
    assert len(reg.resultados) == 3
    assert all(r.estado == FAIL for r in reg.resultados)
    assert "otra causa" in reg.resultados[-1].detalle


@pytest.mark.parametrize("status_token,status_db,puntos,esperados", [
    (401, 404, 0, [OK, OK, OK]),
    (200, 200, 2, [FAIL, FAIL, FAIL]),
    (500, 403, None, [FAIL, FAIL, FAIL]),
])
def test_sondas_influx_validan_estado_y_contenido(monkeypatch, status_token, status_db, puntos, esperados):
    def http(metodo, url, timeout, headers=None, cuerpo_json=None):
        if "/configure/database" in url:
            status, body = status_token, []
        elif cuerpo_json["db"] == "fixture2030_inexistente_h11":
            status, body = status_db, {"error": "database not found"}
        else:
            status, body = (500, {"error": "fallo"}) if puntos is None else (200, [{"puntos": puntos}])
        return RespuestaHTTP(status, {}, json.dumps(body).encode(), 1)
    monkeypatch.setattr(influxdb, "http", http)
    reg = registro()
    influxdb.evaluar(cfg(INFLUX_TOKEN="token-de-prueba"), reg, {"sonda"}, True)
    assert [r.estado for r in reg.resultados] == esperados


def test_sonda_database_neo4j_no_acepta_un_error_de_autenticacion(monkeypatch):
    import neo4j as driver
    from neo4j.exceptions import AuthError
    falso = MagicMock()
    falso.session.return_value.__enter__.return_value.run.side_effect = AuthError("credencial rechazada")
    monkeypatch.setattr(driver.GraphDatabase, "driver", lambda *a, **kw: falso)
    reg = registro()
    neo4j.evaluar(cfg(NEO4J_PASSWORD="prueba"), reg, {"sonda"}, True)
    prueba = next(r for r in reg.resultados if r.prueba == "database inexistente")
    assert prueba.estado == FAIL and "credencial" in prueba.detalle


@pytest.mark.parametrize("existen,esperado", [(False, OK), (True, FAIL)])
def test_sondas_mongo_no_declararan_ausentes_recursos_existentes(monkeypatch, existen, esperado):
    import pymongo
    cliente = MagicMock()
    col = cliente.__getitem__.return_value
    col.equipos.find_one.return_value = {"_id": "ZZZ"} if existen else None
    col.list_collection_names.return_value = ["coleccion_inexistente_h11"] if existen else []
    col.__getitem__.return_value.find_one.return_value = None
    cliente.list_database_names.return_value = ["fixture2030_inexistente_h11"] if existen else []
    monkeypatch.setattr(pymongo, "MongoClient", lambda **kw: cliente)
    reg = registro()
    mongodb.evaluar(cfg(), reg, {"sonda"}, True)
    assert [r.estado for r in reg.resultados] == [esperado] * 3


@pytest.mark.parametrize("creada,ttls,esperado", [
    (True, [-2, 1490, -2], OK),
    (True, [-2, -2, -2], FAIL),
    (False, [-2], FAIL),
])
def test_redis_expiracion_exige_haber_observado_ttl_positivo(monkeypatch, creada, ttls, esperado):
    import redis
    cliente = MagicMock()
    cliente.exists.return_value = 0
    cliente.pttl.side_effect = ttls
    cliente.set.return_value = creada
    cliente.ping.side_effect = redis.exceptions.ConnectionError("sin listener")
    monkeypatch.setattr(redis, "Redis", lambda **kw: cliente)
    monkeypatch.setattr(redis_kv.time, "sleep", lambda _: None)
    reg = registro()
    redis_kv.evaluar(cfg(REDIS_SONDA_EXPIRACION="1"), reg, {"sonda"}, True)
    prueba = next(r for r in reg.resultados if r.prueba == "clave expirada")
    assert prueba.estado == esperado


@pytest.mark.parametrize("correcto,esperado", [(True, OK), (False, FAIL)])
def test_iris_sondas_distinguen_ausencia_de_permisos_y_recursos_presentes(monkeypatch, correcto, esperado):
    import iris as driver
    from iris import dbapi as driver_sql
    conexion_sql = MagicMock()
    conexion_sql.cursor.return_value.fetchall.return_value = [] if correcto else [("P-999",)]
    monkeypatch.setattr(driver_sql, "connect", lambda *a, **kw: conexion_sql)
    nativo = MagicMock()
    def llamar(clase, metodo, *args):
        if metodo == "ObtenerActa":
            return json.dumps({"ok": 0, "error": "NO_ENCONTRADO"} if correcto else {"ok": 1, "acta": {}})
        if clase == "Fixture.ClaseInexistenteH11":
            raise RuntimeError("<CLASS DOES NOT EXIST>" if correcto else "<PROTECT>")
        if metodo == "Exists":
            return 0 if correcto else 1
        raise AssertionError((clase, metodo))
    nativo.classMethodValue.side_effect = llamar
    monkeypatch.setattr(driver, "connect", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(driver, "createIRIS", lambda _: nativo)
    reg = registro()
    iris.evaluar(cfg(IRIS_PASSWORD="prueba"), reg, {"sonda"}, True)
    assert [r.estado for r in reg.resultados] == [esperado] * 3

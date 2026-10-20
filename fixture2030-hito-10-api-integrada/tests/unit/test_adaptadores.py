"""Traducción de errores de cada driver (sección 5.2) y reglas puras de los adaptadores.

Usan las clases de excepción reales de cada cliente, sin conectarse a ninguna base.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from cassandra import OperationTimedOut, ReadTimeout, Unavailable
from cassandra.cluster import NoHostAvailable
from neo4j import exceptions as neo4j_errors
from pymongo import errors as mongo_errors
from redis import exceptions as redis_errors

from app.adapters import (
    cassandra_adapter,
    influx_adapter,
    iris_adapter,
    mongo_adapter,
    neo4j_adapter,
    redis_adapter,
)
from app.core.errores import DependenciaNoDisponible, DependenciaTimeout


@pytest.mark.parametrize(
    ("traducir", "excepcion", "esperado"),
    [
        (mongo_adapter._traducir, mongo_errors.NetworkTimeout("x"), DependenciaTimeout),
        (neo4j_adapter._traducir, neo4j_errors.AuthError("x"), DependenciaNoDisponible),
        (cassandra_adapter._traducir, NoHostAvailable("x", {}), DependenciaNoDisponible),
        (redis_adapter._traducir, redis_errors.TimeoutError("x"), DependenciaTimeout),
        (influx_adapter._traducir, httpx.ReadTimeout("x"), DependenciaTimeout),
        (iris_adapter._traducir, iris_adapter._TimeoutIris(), DependenciaTimeout),
    ],
)
def test_traduccion_de_errores_del_driver(traducir, excepcion, esperado):
    error = traducir(excepcion)
    assert isinstance(error, esperado)
    assert "x" not in error.mensaje.split("'")[0]  # el mensaje del driver no pasa al consumidor


@pytest.mark.parametrize(
    "traducir",
    [mongo_adapter._traducir, neo4j_adapter._traducir, cassandra_adapter._traducir,
     redis_adapter._traducir, influx_adapter._traducir],
)
def test_error_de_programacion_no_se_disfraza_de_dependencia(traducir):
    assert traducir(KeyError("campo")) is None  # termina en 500, no en 503


def test_neo4j_transaccion_vencida_es_timeout():
    # El driver informa el timeout del servidor con este código de estado.
    class TransaccionVencida(Exception):
        code = "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration"

    assert isinstance(neo4j_adapter._traducir(TransaccionVencida()), DependenciaTimeout)


def test_neo4j_database_inexistente_es_dependencia_no_disponible():
    # Hito 11: NEO4J_DATABASE incorrecta respondía 500; es un contexto inválido de la fuente.
    class BaseInexistente(Exception):
        code = "Neo.ClientError.Database.DatabaseNotFound"

    assert isinstance(neo4j_adapter._traducir(BaseInexistente()), DependenciaNoDisponible)


def test_influx_intervalos_son_lista_cerrada():
    assert set(influx_adapter.INTERVALOS) == {"10s", "1m", "5m"}
    assert "$partido" in influx_adapter._SQL_SERIE and "$desde" in influx_adapter._SQL_SERIE


def test_cypher_solo_usa_parametros():
    for cypher in (neo4j_adapter.CYPHER_EVENTOS_PARTIDO,):
        assert "$codigo" in cypher and "{codigo}" not in cypher


def test_uuid_v4_no_es_cursor_valido():
    from app.core.errores import ErrorValidacion
    from app.services.comentarios_service import validar_cursor

    with pytest.raises(ErrorValidacion):
        validar_cursor(str(uuid.uuid4()))


class _DatabaseFalsa:
    """Database en memoria: MongoDB devuelve vacío sin error si el nombre es incorrecto."""

    def __init__(self, colecciones):
        self.colecciones = colecciones
        self.listados = 0
        self.equipos = self

    def list_collection_names(self, filter=None):  # noqa: A002 - misma firma que pymongo
        self.listados += 1
        return list(self.colecciones)

    def find_one(self, *args, **kwargs):
        return None


def test_mongo_database_incorrecta_no_se_confunde_con_recurso_inexistente():
    # Hito 11: antes respondía 404 "no existe la selección"; ahora la fuente queda no disponible.
    from app.config.settings import Settings

    adaptador = mongo_adapter.MongoAdapter(Settings(_env_file=None))  # MongoClient no conecta hasta operar
    adaptador._db = _DatabaseFalsa([])
    with pytest.raises(DependenciaNoDisponible):
        adaptador.obtener_equipo("ARG")


def test_mongo_contexto_se_verifica_una_sola_vez():
    from app.config.settings import Settings

    adaptador = mongo_adapter.MongoAdapter(Settings(_env_file=None))
    adaptador._db = _DatabaseFalsa(["equipos", "jugadores"])
    assert adaptador.obtener_equipo("XYZ") is None  # ausencia válida
    assert adaptador.obtener_equipo("ABC") is None
    assert adaptador._db.listados == 1
    adaptador.cerrar()

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
        (mongo_adapter._traducir, mongo_errors.ServerSelectionTimeoutError("x"), DependenciaNoDisponible),
        (mongo_adapter._traducir, mongo_errors.OperationFailure("auth", code=18), DependenciaNoDisponible),
        (mongo_adapter._traducir, mongo_errors.NetworkTimeout("x"), DependenciaTimeout),
        (mongo_adapter._traducir, mongo_errors.ExecutionTimeout("x"), DependenciaTimeout),
        (neo4j_adapter._traducir, neo4j_errors.ServiceUnavailable("x"), DependenciaNoDisponible),
        (neo4j_adapter._traducir, neo4j_errors.AuthError("x"), DependenciaNoDisponible),
        (cassandra_adapter._traducir, NoHostAvailable("x", {}), DependenciaNoDisponible),
        (cassandra_adapter._traducir, Unavailable("x"), DependenciaNoDisponible),
        (cassandra_adapter._traducir, OperationTimedOut("x"), DependenciaTimeout),
        (cassandra_adapter._traducir, ReadTimeout("x"), DependenciaTimeout),
        (redis_adapter._traducir, redis_errors.ConnectionError("x"), DependenciaNoDisponible),
        (redis_adapter._traducir, redis_errors.AuthenticationError("x"), DependenciaNoDisponible),
        (redis_adapter._traducir, redis_errors.TimeoutError("x"), DependenciaTimeout),
        (influx_adapter._traducir, httpx.ConnectError("x"), DependenciaNoDisponible),
        (influx_adapter._traducir, influx_adapter._RespuestaInvalida("HTTP 401"), DependenciaNoDisponible),
        (influx_adapter._traducir, httpx.ReadTimeout("x"), DependenciaTimeout),
        (iris_adapter._traducir, RuntimeError("<COMMUNICATION LINK ERROR>"), DependenciaNoDisponible),
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


def test_cassandra_orden_por_timeuuid():
    viejo = cassandra_adapter.nuevo_timeuuid(datetime(2030, 6, 15, 20, 15, tzinfo=UTC))
    nuevo = cassandra_adapter.nuevo_timeuuid(datetime(2030, 6, 15, 20, 16, tzinfo=UTC))
    assert viejo.version == 1
    assert sorted([viejo, nuevo], key=cassandra_adapter._orden_timeuuid) == [viejo, nuevo]


def test_influx_intervalos_son_lista_cerrada():
    assert set(influx_adapter.INTERVALOS) == {"10s", "1m", "5m"}
    assert "$partido" in influx_adapter._SQL_SERIE and "$desde" in influx_adapter._SQL_SERIE


def test_cypher_solo_usa_parametros():
    for cypher in (neo4j_adapter.CYPHER_FICHA_PARTIDO, neo4j_adapter.CYPHER_EVENTOS_PARTIDO, neo4j_adapter.CYPHER_RIVALES):
        assert "$codigo" in cypher and "{codigo}" not in cypher


def test_uuid_v4_no_es_cursor_valido():
    from app.core.errores import ErrorValidacion
    from app.services.comentarios_service import validar_cursor

    with pytest.raises(ErrorValidacion):
        validar_cursor(str(uuid.uuid4()))

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.dependencias import Adaptadores
from app.main import crear_app
from tests.unit.dobles import (
    CassandraDoble,
    InfluxDoble,
    IrisDoble,
    MongoDoble,
    Neo4jDoble,
    RedisDoble,
)


@pytest.fixture
def adaptadores() -> Adaptadores:
    return Adaptadores(
        mongodb=MongoDoble(),
        neo4j=Neo4jDoble(),
        cassandra=CassandraDoble(),
        redis=RedisDoble(),
        influxdb=InfluxDoble(),
        iris=IrisDoble(),
    )


@pytest.fixture
def cliente(adaptadores: Adaptadores) -> Iterator[TestClient]:
    # _env_file=None: las pruebas unitarias no dependen del .env local.
    app = crear_app(adaptadores=adaptadores, settings=Settings(_env_file=None))
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def sin_llamadas(adaptadores: Adaptadores) -> bool:
    return all(not a.llamadas for a in adaptadores.como_dict().values())

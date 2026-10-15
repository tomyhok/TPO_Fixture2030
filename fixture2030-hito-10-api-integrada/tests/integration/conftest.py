"""Fixtures de integración: la API real contra las fuentes reales.

Requieren los contenedores levantados y `scripts/preparar_datos.sh` ejecutado.
Si alguna fuente no responde, las pruebas se saltean indicando cuál.
"""

import json
import socket
import threading
from collections.abc import Iterator

import iris
import pytest
import redis
from fastapi.testclient import TestClient

from app.config.settings import Settings, obtener_settings
from app.main import crear_app

_ESQUEMA: dict | None = None


@pytest.fixture(scope="session")
def settings() -> Settings:
    return obtener_settings()


@pytest.fixture(scope="session")
def cliente(settings: Settings) -> Iterator[TestClient]:
    global _ESQUEMA
    app = crear_app(settings=settings)
    with TestClient(app, raise_server_exceptions=False) as c:
        salud = c.get("/health")
        if salud.status_code != 200:
            caidas = [d["nombre"] for d in salud.json()["dependencias"] if d["estado"] != "ok"]
            pytest.skip(f"Fuentes no disponibles: {caidas}. Ver scripts/verificar_conectividad.sh")
        _ESQUEMA = app.openapi()
        yield c


def documentado(respuesta, metodo: str, plantilla: str) -> None:
    """La respuesta real usa un código que el contrato OpenAPI declara para esa operación."""
    assert _ESQUEMA is not None
    codigos = _ESQUEMA["paths"][plantilla][metodo]["responses"]
    assert str(respuesta.status_code) in codigos, (metodo, plantilla, respuesta.status_code, list(codigos))


@pytest.fixture(scope="session")
def redis_directo(settings: Settings) -> Iterator[redis.Redis]:
    """Acceso directo solo para preparar escenarios (sesión expirada, caché vacía)."""
    cliente = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password.get_secret_value() or None,
        decode_responses=True,
    )
    yield cliente
    cliente.close()


@pytest.fixture
def actas_reiniciadas(settings: Settings) -> None:
    """Deja P-001 (En Juego), P-002 (Programado) y P-003 (Finalizado) en su estado inicial."""
    conexion = iris.connect(
        settings.iris_host,
        settings.iris_port,
        settings.iris_namespace,
        settings.iris_user,
        settings.iris_password.get_secret_value(),
    )
    try:
        resultado = json.loads(iris.createIRIS(conexion).classMethodValue("Fixture.API", "CargarMuestra"))
        assert resultado["ok"] == 1
    finally:
        conexion.close()


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def servidor_mudo() -> Iterator[int]:
    """Acepta conexiones TCP y nunca responde: simula una dependencia lenta o colgada."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen()
    abiertas: list[socket.socket] = []
    activo = True

    def aceptar() -> None:
        while activo:
            try:
                conexion, _ = servidor.accept()
                abiertas.append(conexion)
            except OSError:
                return

    threading.Thread(target=aceptar, daemon=True).start()
    yield servidor.getsockname()[1]
    activo = False
    servidor.close()
    for conexion in abiertas:
        conexion.close()

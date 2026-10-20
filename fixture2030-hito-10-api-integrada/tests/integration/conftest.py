"""Fixtures de integración: la API real contra las fuentes reales.

Requieren los contenedores levantados y `scripts/preparar_datos.sh` ejecutado.
Solo se omite la lectura cuya configuración obligatoria falta; una falla de una fuente configurada hace fallar su prueba.
"""

import socket
import threading
from collections.abc import Iterator

import pytest
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
        _ESQUEMA = app.openapi()
        yield c


def documentado(respuesta, metodo: str, plantilla: str) -> None:
    """La respuesta real usa un código que el contrato OpenAPI declara para esa operación."""
    assert _ESQUEMA is not None
    codigos = _ESQUEMA["paths"][plantilla][metodo]["responses"]
    assert str(respuesta.status_code) in codigos, (metodo, plantilla, respuesta.status_code, list(codigos))


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

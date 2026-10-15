"""Request ID y logs (RF18, RNF10).

El request ID se guarda en una ContextVar para que cualquier línea de log
(ruta, servicio o adaptador) lo incluya sin pasarlo por parámetro. Los logs
registran ruta, método, dependencia, operación, resultado y duración; nunca
cuerpos de request, credenciales ni consultas completas.
"""

import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar

request_id_actual: ContextVar[str] = ContextVar("request_id", default="-")

_PATRON_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def nuevo_request_id(recibido: str | None) -> str:
    """Reutiliza el X-Request-ID del cliente si es seguro; si no, genera uno."""
    if recibido and _PATRON_REQUEST_ID.match(recibido):
        return recibido
    return str(uuid.uuid4())


class _FiltroRequestId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_actual.get()
        return True


def configurar_logs(nivel: str) -> None:
    raiz = logging.getLogger("fixture2030")
    if getattr(raiz, "_configurado", False):
        raiz.setLevel(nivel.upper())
        return
    manejador = logging.StreamHandler(sys.stdout)
    formato = logging.Formatter(
        "%(asctime)sZ %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formato.converter = time.gmtime  # marcas de tiempo en UTC
    manejador.setFormatter(formato)
    manejador.addFilter(_FiltroRequestId())
    raiz.addHandler(manejador)
    raiz.setLevel(nivel.upper())
    raiz.propagate = False
    raiz._configurado = True  # type: ignore[attr-defined]

    # Los drivers son muy verbosos y pueden registrar hosts; solo advertencias.
    for nombre in ("neo4j", "cassandra", "pymongo", "httpx", "httpcore"):
        logging.getLogger(nombre).setLevel(logging.WARNING)


def logger(nombre: str) -> logging.Logger:
    return logging.getLogger(f"fixture2030.{nombre}")

"""Lectura de sesion:<id> y su TTL. No escribe caché ni reservas de idempotencia."""

from typing import Any

import redis
from redis import exceptions as redis_errors
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI

DEPENDENCIA = "redis"
CAMPOS_SESION_PUBLICOS = ("usuario_id", "rol", "estado")


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, redis_errors.TimeoutError):
        return timeout(DEPENDENCIA)
    if isinstance(exc, (redis_errors.ConnectionError, OSError)):
        # Incluye AuthenticationError y BusyLoadingError.
        return no_disponible(DEPENDENCIA)
    return None


class RedisAdapter:
    def __init__(self, settings: Settings):
        self._cliente = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password.get_secret_value() or None,
            socket_connect_timeout=settings.timeout_conexion_s,
            socket_timeout=settings.timeout_operacion_s,
            # Sin reintentos ocultos: el tiempo máximo de espera es el configurado.
            retry=Retry(NoBackoff(), 0),
            decode_responses=True,
            client_name="fixture2030-api",
        )

    # --------------------------------------------------------------- sesiones
    def leer_sesion(self, id_sesion: str) -> dict[str, Any] | None:
        clave = f"sesion:{id_sesion}"
        with operacion(DEPENDENCIA, "sesion.hmget_ttl", _traducir):
            pipe = self._cliente.pipeline(transaction=False)
            pipe.hmget(clave, *CAMPOS_SESION_PUBLICOS)
            pipe.ttl(clave)
            valores, ttl = pipe.execute()
        # TTL -2: la clave no existe (nunca existió o ya expiró).
        if ttl == -2 or all(v is None for v in valores):
            return None
        sesion: dict[str, Any] = dict(zip(CAMPOS_SESION_PUBLICOS, valores, strict=True))
        sesion["ttl_restante_s"] = ttl if ttl >= 0 else None  # -1 = sin expiración
        return sesion

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._cliente.ping()

    def cerrar(self) -> None:
        self._cliente.close()

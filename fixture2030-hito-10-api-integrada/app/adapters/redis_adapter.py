"""Adaptador clave/valor: Redis (Hito 7).

Usa exactamente las claves del Hito 7:
  * `sesion:<id_sesion>`          Hash con TTL de 1800 s (PA1, PA2);
  * `cache:partido:<codigo>`      String JSON con TTL de 300 s (PA3).
y agrega una sola familia nueva, propia de la API:
  * `idem:<operacion>:<clave>`    String JSON con TTL de 24 h para la
                                  idempotencia de las escrituras.

Distingue "clave inexistente" (respuesta válida de Redis: nil / TTL -2) de
"Redis no disponible" (excepción del cliente), que es lo que pide 5.8.
"""

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

    def borrar_sesion(self, id_sesion: str) -> int:
        with operacion(DEPENDENCIA, "sesion.del", _traducir):
            return int(self._cliente.delete(f"sesion:{id_sesion}"))

    # ------------------------------------------------------------------ caché
    def leer_cache_partido(self, codigo: str) -> str | None:
        with operacion(DEPENDENCIA, "cache_partido.get", _traducir):
            return self._cliente.get(f"cache:partido:{codigo}")

    def guardar_cache_partido(self, codigo: str, valor_json: str, ttl_s: int) -> None:
        with operacion(DEPENDENCIA, "cache_partido.set_ex", _traducir):
            self._cliente.set(f"cache:partido:{codigo}", valor_json, ex=ttl_s)

    # ----------------------------------------------------------- idempotencia
    def reservar_idempotencia(self, clave: str, valor_json: str, ttl_s: int) -> bool:
        """SET NX: True si la clave era nueva y quedó reservada para esta request."""
        with operacion(DEPENDENCIA, "idempotencia.set_nx", _traducir):
            return bool(self._cliente.set(clave, valor_json, nx=True, ex=ttl_s))

    def leer_idempotencia(self, clave: str) -> str | None:
        with operacion(DEPENDENCIA, "idempotencia.get", _traducir):
            return self._cliente.get(clave)

    def completar_idempotencia(self, clave: str, valor_json: str) -> None:
        with operacion(DEPENDENCIA, "idempotencia.set_xx", _traducir):
            self._cliente.set(clave, valor_json, xx=True, keepttl=True)

    def liberar_idempotencia(self, clave: str) -> None:
        with operacion(DEPENDENCIA, "idempotencia.del", _traducir):
            self._cliente.delete(clave)

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._cliente.ping()

    def cerrar(self) -> None:
        self._cliente.close()

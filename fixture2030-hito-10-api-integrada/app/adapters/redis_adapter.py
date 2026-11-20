"""Lectura de sesion:<id> y su TTL (Hito 10) y escrituras acotadas del portal de demostración."""

from datetime import UTC, datetime
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

    # ----------------------------------------------------------------- portal
    # Escrituras del portal de demostración, con las mismas claves del Hito 7:
    # sesion:<id> (hash + TTL), contador:partido:<p>:visitas, conectados:partido:<p> (set)
    # y encuesta:partido:<p>:figura (sorted set). Fuera del contrato de solo lectura del Hito 10.
    def crear_sesion(self, alias: str, equipo_favorito: str | None, ttl_s: int) -> dict[str, Any]:
        with operacion(DEPENDENCIA, "sesion.crear", _traducir):
            # Secuencia propia desde 5000 para no pisar las muestras (S-0001.., U-1001..).
            self._cliente.set("seq:portal:usuario", 5000, nx=True)
            n = self._cliente.incr("seq:portal:usuario")
            id_sesion, usuario_id = f"S-{n}", f"U-{n}"
            ahora = datetime.now(UTC).isoformat(timespec="seconds")
            pipe = self._cliente.pipeline(transaction=True)
            pipe.hset(f"sesion:{id_sesion}", mapping={
                "id_sesion": id_sesion, "usuario_id": usuario_id, "rol": "fan", "estado": "activa",
                "dispositivo": "web", "creada_en": ahora, "ultimo_acceso": ahora, "paginas_vistas": 0,
                "alias": alias, "equipo_favorito": equipo_favorito or "",
            })
            pipe.expire(f"sesion:{id_sesion}", ttl_s)
            pipe.execute()
        return {"id_sesion": id_sesion, "usuario_id": usuario_id, "ttl_restante_s": ttl_s}

    def leer_sesion_portal(self, id_sesion: str) -> dict[str, Any] | None:
        clave = f"sesion:{id_sesion}"
        campos = ("usuario_id", "rol", "estado", "alias", "equipo_favorito")
        with operacion(DEPENDENCIA, "sesion.hmget_ttl", _traducir):
            pipe = self._cliente.pipeline(transaction=False)
            pipe.hmget(clave, *campos)
            pipe.ttl(clave)
            valores, ttl = pipe.execute()
        if ttl == -2 or valores[0] is None:
            return None
        datos = dict(zip(campos, valores, strict=True))
        datos["alias"] = datos["alias"] or datos["usuario_id"]
        datos["equipo_favorito"] = datos["equipo_favorito"] or None
        return {"id_sesion": id_sesion, **datos, "ttl_restante_s": ttl if ttl >= 0 else None}

    def cerrar_sesion(self, id_sesion: str) -> bool:
        with operacion(DEPENDENCIA, "sesion.del", _traducir):
            return bool(self._cliente.delete(f"sesion:{id_sesion}"))

    def registrar_visita(self, codigo: str, usuario_id: str | None, id_sesion: str | None) -> None:
        with operacion(DEPENDENCIA, "partido.visita", _traducir):
            pipe = self._cliente.pipeline(transaction=False)
            pipe.incr(f"contador:partido:{codigo}:visitas")
            if usuario_id:
                pipe.sadd(f"conectados:partido:{codigo}", usuario_id)
                pipe.expire(f"conectados:partido:{codigo}", 10800)
                pipe.hincrby(f"sesion:{id_sesion}", "paginas_vistas", 1)
                pipe.hset(f"sesion:{id_sesion}", "ultimo_acceso", datetime.now(UTC).isoformat(timespec="seconds"))
            pipe.execute()

    def estado_vivo(self, codigo: str, usuario_id: str | None) -> dict[str, Any]:
        with operacion(DEPENDENCIA, "partido.vivo", _traducir):
            pipe = self._cliente.pipeline(transaction=False)
            pipe.get(f"contador:partido:{codigo}:visitas")
            pipe.scard(f"conectados:partido:{codigo}")
            pipe.zrevrange(f"encuesta:partido:{codigo}:figura", 0, 9, withscores=True)
            pipe.sismember(f"encuesta:partido:{codigo}:votantes", usuario_id or "")
            visitas, conectados, ranking, voto = pipe.execute()
        return {
            "visitas": int(visitas or 0),
            "conectados": conectados,
            "encuesta": [{"id_jugador": j, "votos": int(v)} for j, v in ranking],
            "ya_voto": bool(voto),
        }

    def votar_figura(self, codigo: str, usuario_id: str, id_jugador: str) -> bool:
        """False si el usuario ya había votado en este partido (un voto por usuario)."""
        with operacion(DEPENDENCIA, "encuesta.zincrby", _traducir):
            if not self._cliente.sadd(f"encuesta:partido:{codigo}:votantes", usuario_id):
                return False
            self._cliente.zincrby(f"encuesta:partido:{codigo}:figura", 1, id_jugador)
            return True

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._cliente.ping()

    def cerrar(self) -> None:
        self._cliente.close()

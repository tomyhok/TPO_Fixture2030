"""Idempotencia de las escrituras (RF19, RNF14).

Las creaciones (comentario y evento del acta) exigen el header
`Idempotency-Key`. La clave se reserva en Redis con SET NX antes de escribir:

  * clave nueva                         -> se ejecuta la escritura y se guarda la respuesta;
  * misma clave + mismo cuerpo, ya hecha -> se devuelve la respuesta guardada, sin escribir;
  * misma clave + otro cuerpo            -> 409 CONFLICTO_IDEMPOTENCIA;
  * misma clave todavía en curso         -> 409 CONFLICTO_IDEMPOTENCIA (reintentar luego).

Si la escritura falla, la clave se libera para que el cliente pueda reintentar.
Sin Redis no hay garantía de no duplicar, así que la escritura no se hace (503).
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.core.errores import ConflictoIdempotencia, ErrorDependencia
from app.core.observabilidad import logger

_log = logger("idempotencia")


def _huella(cuerpo: dict[str, Any]) -> str:
    serializado = json.dumps(cuerpo, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


class Idempotencia:
    def __init__(self, redis_adapter: Any, ttl_s: int):
        self._redis = redis_adapter
        self._ttl_s = ttl_s

    def ejecutar(
        self,
        operacion: str,
        clave: str,
        cuerpo: dict[str, Any],
        escribir: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        """Devuelve (respuesta, repetida). `repetida` es True si no se volvió a escribir."""
        clave_redis = f"idem:{operacion}:{clave.lower()}"
        huella = _huella(cuerpo)
        reserva = json.dumps({"huella": huella, "estado": "en_curso"})

        if not self._redis.reservar_idempotencia(clave_redis, reserva, self._ttl_s):
            previo = self._redis.leer_idempotencia(clave_redis)
            if previo is None:
                # Expiró entre el SET NX y el GET: se intenta reservar una sola vez más.
                if not self._redis.reservar_idempotencia(clave_redis, reserva, self._ttl_s):
                    raise ConflictoIdempotencia("La Idempotency-Key está en uso; reintente más tarde.")
            else:
                datos = json.loads(previo)
                if datos.get("huella") != huella:
                    raise ConflictoIdempotencia(
                        "La Idempotency-Key ya se usó con un cuerpo distinto. Genere una clave nueva."
                    )
                if datos.get("estado") != "completado":
                    raise ConflictoIdempotencia(
                        "Hay una solicitud con esta Idempotency-Key en curso; reintente más tarde."
                    )
                _log.info("operacion=%s resultado=repetida", operacion)
                return datos["respuesta"], True

        try:
            respuesta = escribir()
        except Exception:
            self._liberar(clave_redis)
            raise

        completado = json.dumps(
            {"huella": huella, "estado": "completado", "respuesta": respuesta}, default=str
        )
        try:
            self._redis.completar_idempotencia(clave_redis, completado)
        except ErrorDependencia:
            # La escritura ya se hizo: se informa éxito. Un reintento con la misma
            # clave recibirá 409 "en curso" hasta que venza el TTL, nunca un duplicado.
            _log.warning("operacion=%s resultado=no_se_pudo_registrar_respuesta", operacion)
        return respuesta, False

    def _liberar(self, clave_redis: str) -> None:
        try:
            self._redis.liberar_idempotencia(clave_redis)
        except ErrorDependencia:
            _log.warning("resultado=no_se_pudo_liberar_clave_idempotencia")

"""Lectura representativa del motor, con validación de entrada."""

from typing import Any

from app.core.errores import SesionNoVigente
from app.schemas.sesiones import Sesion


class SesionesService:
    def __init__(self, redis: Any):
        self._redis = redis

    def obtener(self, id_sesion: str) -> Sesion:
        # La lectura no renueva el TTL: un GET no tiene efectos.
        datos = self._redis.leer_sesion(id_sesion)
        if datos is None:
            raise SesionNoVigente(f"No existe una sesión vigente con id '{id_sesion}'.")
        return Sesion(id_sesion=id_sesion, **datos)

"""Consulta de la vista persistente de IRIS, sin reglas de escritura HTTP."""
from typing import Any
from app.core.errores import RecursoNoEncontrado
from app.schemas.actas import Acta

class ActasService:
    def __init__(self, iris: Any):
        self._iris = iris

    def obtener(self, codigo: str) -> Acta:
        datos = self._iris.obtener_acta(codigo)
        if datos is None:
            raise RecursoNoEncontrado(f"No existe el acta del partido '{codigo}'.")
        return Acta.model_validate(datos)

"""Una lectura documental, sin combinar fuentes."""
from typing import Any
from app.core.errores import RecursoNoEncontrado
from app.schemas.equipos import EquipoDetalle

class EquiposService:
    def __init__(self, mongo: Any):
        self._mongo = mongo

    def obtener_equipo(self, codigo_iso: str) -> EquipoDetalle:
        doc = self._mongo.obtener_equipo(codigo_iso)
        if doc is None:
            raise RecursoNoEncontrado(f"No existe la selección '{codigo_iso}'.")
        return EquipoDetalle.model_validate(doc)

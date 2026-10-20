"""Lectura de eventos en Neo4j; sin caché Redis."""
from typing import Any
from app.core.errores import RecursoNoEncontrado
from app.schemas.partidos import EventosPartido

class PartidosService:
    def __init__(self, neo4j: Any):
        self._neo4j = neo4j

    def eventos(self, codigo: str, limit: int) -> EventosPartido:
        fila = self._neo4j.eventos_partido(codigo, limit)
        if fila is None:
            raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")
        return EventosPartido.model_validate(fila)

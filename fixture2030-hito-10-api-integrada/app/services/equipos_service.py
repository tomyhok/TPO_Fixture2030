"""Casos de uso CU01–CU04 (MongoDB) y CU07 (rivales en Neo4j)."""

from typing import Any

from app.core.errores import RecursoNoEncontrado
from app.schemas.equipos import (
    EquipoDetalle,
    JugadorDetalle,
    PaginaEquipos,
    PaginaJugadores,
)
from app.schemas.partidos import RivalesEquipo


class EquiposService:
    def __init__(self, mongo: Any, neo4j: Any):
        self._mongo = mongo
        self._neo4j = neo4j

    def obtener_equipo(self, codigo_iso: str) -> EquipoDetalle:
        doc = self._mongo.obtener_equipo(codigo_iso)
        if doc is None:
            raise RecursoNoEncontrado(f"No existe la selección '{codigo_iso}'.")
        return EquipoDetalle.model_validate(doc)

    def listar_equipos(
        self, confederacion: str | None, grupo: str | None, page: int, size: int
    ) -> PaginaEquipos:
        items, total = self._mongo.listar_equipos(confederacion, grupo, page, size)
        return PaginaEquipos(items=items, page=page, size=size, total=total)

    def plantel(self, codigo_iso: str, posicion: str | None, page: int, size: int) -> PaginaJugadores:
        # Se distingue "selección inexistente" (404) de "sin jugadores en esa posición" (200 vacío).
        if not self._mongo.existe_equipo(codigo_iso):
            raise RecursoNoEncontrado(f"No existe la selección '{codigo_iso}'.")
        items, total = self._mongo.listar_jugadores(codigo_iso, posicion, page, size)
        return PaginaJugadores(codigo_iso=codigo_iso, items=items, page=page, size=size, total=total)

    def obtener_jugador(self, id_jugador: str) -> JugadorDetalle:
        doc = self._mongo.obtener_jugador(id_jugador)
        if doc is None:
            raise RecursoNoEncontrado(f"No existe el jugador '{id_jugador}'.")
        return JugadorDetalle.model_validate(doc)

    def rivales(self, codigo_iso: str, limit: int) -> RivalesEquipo:
        fila = self._neo4j.rivales(codigo_iso, limit)
        if fila is None:
            raise RecursoNoEncontrado(f"No existe la selección '{codigo_iso}' en el fixture.")
        return RivalesEquipo.model_validate(fila)

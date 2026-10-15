"""Casos de uso CU05 (ficha con caché Redis + Neo4j) y CU06 (eventos en Neo4j)."""

from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from app.core.errores import ErrorDependencia, RecursoNoEncontrado
from app.core.observabilidad import logger
from app.schemas.partidos import EventosPartido, FichaPartido

_log = logger("servicio.partidos")


class EstadoCache(StrEnum):
    HIT = "HIT"  # respondido desde Redis
    MISS = "MISS"  # leído de Neo4j y guardado en Redis
    BYPASS = "BYPASS"  # Redis no disponible: respuesta degradada, directo de Neo4j


class PartidosService:
    def __init__(self, neo4j: Any, redis: Any, ttl_cache_s: int):
        self._neo4j = neo4j
        self._redis = redis
        self._ttl_cache_s = ttl_cache_s

    def ficha(self, codigo: str) -> tuple[FichaPartido, EstadoCache]:
        redis_disponible = True
        try:
            en_cache = self._redis.leer_cache_partido(codigo)
        except ErrorDependencia:
            redis_disponible = False
            en_cache = None
            _log.warning("cache=bypass motivo=redis_no_disponible codigo=%s", codigo)

        if en_cache is not None:
            try:
                return FichaPartido.model_validate_json(en_cache), EstadoCache.HIT
            except ValidationError:
                # Entrada con otro formato (p. ej. la muestra del Hito 7): se trata
                # como miss y se reemplaza por la ficha con el contrato de la API.
                _log.info("cache=formato_invalido codigo=%s", codigo)

        datos = self._neo4j.ficha_partido(codigo)
        if datos is None:
            raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")
        ficha = FichaPartido.model_validate(datos)

        if not redis_disponible:
            return ficha, EstadoCache.BYPASS
        try:
            self._redis.guardar_cache_partido(codigo, ficha.model_dump_json(), self._ttl_cache_s)
        except ErrorDependencia:
            return ficha, EstadoCache.BYPASS
        return ficha, EstadoCache.MISS

    def eventos(self, codigo: str, limit: int) -> EventosPartido:
        fila = self._neo4j.eventos_partido(codigo, limit)
        if fila is None:
            raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")
        return EventosPartido.model_validate(fila)

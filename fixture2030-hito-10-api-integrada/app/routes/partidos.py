"""Rutas del módulo de grafos (CU05–CU07). CU05 combina Neo4j con la caché de Redis."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoIso, CodigoPartido
from app.schemas.partidos import EventosPartido, FichaPartido, RivalesEquipo

router = APIRouter(tags=["Partidos y relaciones (Neo4j)"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/partidos/{codigo_partido}",
    response_model=FichaPartido,
    summary="CU05 - Ficha de un partido (caché Redis + Neo4j)",
    description=(
        "Cache-aside: primero `cache:partido:<codigo>` en Redis (TTL 300 s); si no está, "
        "Cypher parametrizado en Neo4j y se guarda en la caché. Si Redis no está disponible "
        "la respuesta es degradada (`X-Cache: BYPASS`) y se lee directo de Neo4j."
    ),
    responses={
        200: {
            "headers": {
                "X-Cache": {
                    "description": "HIT (Redis), MISS (Neo4j y se cacheó) o BYPASS (Redis caído).",
                    "schema": {"type": "string", "enum": ["HIT", "MISS", "BYPASS"]},
                }
            }
        },
        **respuestas(404, 503, 504),
    },
)
def ficha_partido(codigo_partido: CodigoPartido, response: Response, svc: Svc) -> FichaPartido:
    ficha, estado_cache = svc.partidos.ficha(codigo_partido)
    response.headers["X-Cache"] = estado_cache.value
    return ficha


@router.get(
    "/partidos/{codigo_partido}/eventos",
    response_model=EventosPartido,
    summary="CU06 - Eventos de un partido",
    description="404 si el partido no existe; 200 con `eventos: []` si existe y no tiene eventos.",
    responses=respuestas(404, 503, 504),
)
def eventos_partido(
    codigo_partido: CodigoPartido,
    svc: Svc,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> EventosPartido:
    return svc.partidos.eventos(codigo_partido, limit)


@router.get(
    "/equipos/{codigo_iso}/rivales",
    response_model=RivalesEquipo,
    summary="CU07 - Rivales de una selección",
    responses=respuestas(404, 503, 504),
)
def rivales(
    codigo_iso: CodigoIso,
    svc: Svc,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> RivalesEquipo:
    return svc.equipos.rivales(codigo_iso, limit)

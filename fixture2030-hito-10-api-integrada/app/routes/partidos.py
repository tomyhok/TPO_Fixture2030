"""Un recorrido Cypher parametrizado y acotado."""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoPartido
from app.schemas.partidos import EventosPartido
router = APIRouter(tags=["Eventos (Neo4j)"])
Svc = Annotated[Servicios, Depends(servicios)]

@router.get("/partidos/{codigo_partido}/eventos", response_model=EventosPartido,
            summary="Eventos de un partido", responses=respuestas(404, 503, 504))
def eventos_partido(codigo_partido: CodigoPartido, svc: Svc,
                    limit: Annotated[int, Query(ge=1, le=200)] = 50) -> EventosPartido:
    return svc.partidos.eventos(codigo_partido, limit)

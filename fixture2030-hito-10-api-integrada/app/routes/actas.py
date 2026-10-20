"""Vista SQL de objetos persistentes en IRIS; solo lectura."""
from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoPartido
from app.schemas.actas import Acta
router = APIRouter(tags=["Actas (IRIS)"])
Svc = Annotated[Servicios, Depends(servicios)]

@router.get("/partidos-oficiales/{codigo_partido}", response_model=Acta,
            summary="Vista del acta persistente", responses=respuestas(404, 503, 504))
def obtener_acta(codigo_partido: CodigoPartido, svc: Svc) -> Acta:
    return svc.actas.obtener(codigo_partido)

"""Lectura documental representativa de MongoDB (Hito 10)."""
from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoIso
from app.schemas.equipos import EquipoDetalle
router = APIRouter(tags=["Equipos (MongoDB)"])
Svc = Annotated[Servicios, Depends(servicios)]

@router.get("/equipos/{codigo_iso}", response_model=EquipoDetalle,
            summary="Ficha de una selección", responses=respuestas(404, 503, 504))
def obtener_equipo(codigo_iso: CodigoIso, svc: Svc) -> EquipoDetalle:
    return svc.equipos.obtener_equipo(codigo_iso)

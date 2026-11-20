"""Rutas del portal de demostración del Fixture 2030 (/portal/api).

Quedan fuera del esquema OpenAPI: el contrato del Hito 10 sigue siendo de seis
lecturas. La sesión del usuario viaja en el header X-Sesion-ID.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import RedirectResponse

from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoIso, CodigoPartido, IdSesion
from app.schemas.comentarios import Comentario
from app.schemas.equipos import EquipoDetalle
from app.schemas.portal import (
    EstadoVivo,
    MuroPortal,
    NuevaSesion,
    NuevoComentario,
    PartidoFixture,
    Plantel,
    SesionPortal,
    Voto,
)

router = APIRouter(prefix="/portal/api", include_in_schema=False)
raiz = APIRouter(include_in_schema=False)
Svc = Annotated[Servicios, Depends(servicios)]
SesionHeader = Annotated[str | None, Header(alias="X-Sesion-ID", pattern=r"^S-\d{4,}$")]


@raiz.get("/")
def inicio() -> RedirectResponse:
    return RedirectResponse("/portal/")


@router.get("/partidos", response_model=list[PartidoFixture])
def partidos(svc: Svc) -> list[PartidoFixture]:
    return svc.portal.partidos()


@router.get("/equipos", response_model=list[EquipoDetalle])
def equipos(svc: Svc) -> list[EquipoDetalle]:
    return svc.portal.equipos()


@router.get("/equipos/{codigo_iso}/plantel", response_model=Plantel)
def plantel(codigo_iso: CodigoIso, svc: Svc) -> Plantel:
    return svc.portal.plantel(codigo_iso)


@router.post("/sesiones", response_model=SesionPortal, status_code=status.HTTP_201_CREATED)
def iniciar_sesion(datos: NuevaSesion, svc: Svc) -> SesionPortal:
    return svc.portal.iniciar_sesion(datos)


@router.get("/sesiones/{id_sesion}", response_model=SesionPortal)
def sesion(id_sesion: IdSesion, svc: Svc) -> SesionPortal:
    return svc.portal.sesion(id_sesion)


@router.delete("/sesiones/{id_sesion}", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(id_sesion: IdSesion, svc: Svc) -> Response:
    svc.portal.cerrar_sesion(id_sesion)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/partidos/{codigo_partido}/muro", response_model=MuroPortal)
def muro(codigo_partido: CodigoPartido, svc: Svc, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> MuroPortal:
    return svc.portal.muro(codigo_partido, limit)


@router.post("/partidos/{codigo_partido}/comentarios", response_model=Comentario,
             status_code=status.HTTP_201_CREATED)
def comentar(codigo_partido: CodigoPartido, datos: NuevoComentario, svc: Svc,
             x_sesion: SesionHeader = None) -> Comentario:
    return Comentario(**svc.portal.comentar(codigo_partido, x_sesion, datos))


@router.get("/partidos/{codigo_partido}/vivo", response_model=EstadoVivo)
def vivo(codigo_partido: CodigoPartido, svc: Svc, x_sesion: SesionHeader = None) -> EstadoVivo:
    return svc.portal.vivo(codigo_partido, x_sesion)


@router.post("/partidos/{codigo_partido}/visitas", response_model=EstadoVivo)
def visita(codigo_partido: CodigoPartido, svc: Svc, x_sesion: SesionHeader = None) -> EstadoVivo:
    return svc.portal.visita(codigo_partido, x_sesion)


@router.post("/partidos/{codigo_partido}/encuesta", response_model=EstadoVivo)
def votar(codigo_partido: CodigoPartido, voto: Voto, svc: Svc, x_sesion: SesionHeader = None) -> EstadoVivo:
    return svc.portal.votar(codigo_partido, x_sesion, voto.id_jugador)

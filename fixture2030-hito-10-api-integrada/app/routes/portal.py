"""Rutas del portal de demostración del Fixture 2030 (/portal/api).

Quedan fuera del esquema OpenAPI: el contrato público son las cinco lecturas, una
por motor. La sesión del usuario viaja en el header X-Sesion-ID.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import RedirectResponse

from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoIso, CodigoPartido, IdSesion
from app.schemas.comunes import PATRON_CODIGO_ISO
from app.schemas.comentarios import Comentario
from app.schemas.equipos import EquipoDetalle
from app.schemas.portal import (
    EstadoVivo,
    MuroPortal,
    NuevaSesion,
    NuevoComentario,
    NuevoEstado,
    PartidoFixture,
    Plantel,
    SesionPortal,
)
from app.schemas.prode import NuevaPrediccion, Prediccion, ResumenPredicciones, TablaPosiciones

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


@router.put("/partidos/{codigo_partido}/estado", response_model=PartidoFixture)
def cambiar_estado(codigo_partido: CodigoPartido, datos: NuevoEstado, svc: Svc,
                   x_sesion: SesionHeader = None) -> PartidoFixture:
    return svc.portal.cambiar_estado(codigo_partido, x_sesion, datos.estado)


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



# ------------------------------------------------------------------- prode (MongoDB)
@router.put("/partidos/{codigo_partido}/prediccion", response_model=Prediccion)
def pronosticar(codigo_partido: CodigoPartido, datos: NuevaPrediccion, svc: Svc,
                x_sesion: SesionHeader = None) -> Prediccion:
    return svc.prode.pronosticar(codigo_partido, x_sesion, datos)


@router.get("/partidos/{codigo_partido}/predicciones", response_model=ResumenPredicciones)
def predicciones_partido(codigo_partido: CodigoPartido, svc: Svc,
                         x_sesion: SesionHeader = None) -> ResumenPredicciones:
    return svc.prode.resumen(codigo_partido, x_sesion)


@router.get("/predicciones", response_model=list[Prediccion])
def mis_predicciones(svc: Svc, x_sesion: SesionHeader = None) -> list[Prediccion]:
    return svc.prode.mias(x_sesion)


@router.get("/posiciones", response_model=TablaPosiciones)
def posiciones(svc: Svc, x_sesion: SesionHeader = None,
               equipo: Annotated[str | None, Query(pattern=PATRON_CODIGO_ISO)] = None,
               limit: Annotated[int, Query(ge=1, le=200)] = 50) -> TablaPosiciones:
    return svc.prode.posiciones(x_sesion, equipo, limit)

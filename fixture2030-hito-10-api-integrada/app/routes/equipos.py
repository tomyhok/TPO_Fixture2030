"""Rutas del módulo documental (CU01–CU04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoIso, IdJugador
from app.schemas.equipos import (
    Confederacion,
    EquipoDetalle,
    Grupo,
    JugadorDetalle,
    PaginaEquipos,
    PaginaJugadores,
    Posicion,
)

router = APIRouter(tags=["Equipos y jugadores (MongoDB)"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/equipos",
    response_model=PaginaEquipos,
    summary="CU02 - Listar selecciones por ranking FIFA",
    responses=respuestas(503, 504),
)
def listar_equipos(
    svc: Svc,
    confederacion: Annotated[Confederacion | None, Query()] = None,
    grupo: Annotated[Grupo | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> PaginaEquipos:
    return svc.equipos.listar_equipos(
        confederacion.value if confederacion else None, grupo.value if grupo else None, page, size
    )


@router.get(
    "/equipos/{codigo_iso}",
    response_model=EquipoDetalle,
    summary="CU01 - Ficha de una selección",
    responses=respuestas(404, 503, 504),
)
def obtener_equipo(codigo_iso: CodigoIso, svc: Svc) -> EquipoDetalle:
    return svc.equipos.obtener_equipo(codigo_iso)


@router.get(
    "/equipos/{codigo_iso}/jugadores",
    response_model=PaginaJugadores,
    summary="CU03 - Plantel de una selección",
    responses=respuestas(404, 503, 504),
)
def plantel(
    codigo_iso: CodigoIso,
    svc: Svc,
    posicion: Annotated[Posicion | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 26,
) -> PaginaJugadores:
    return svc.equipos.plantel(codigo_iso, posicion.value if posicion else None, page, size)


@router.get(
    "/jugadores/{id_jugador}",
    response_model=JugadorDetalle,
    summary="CU04 - Ficha de un jugador",
    responses=respuestas(404, 503, 504),
)
def obtener_jugador(id_jugador: IdJugador, svc: Svc) -> JugadorDetalle:
    return svc.equipos.obtener_jugador(id_jugador)

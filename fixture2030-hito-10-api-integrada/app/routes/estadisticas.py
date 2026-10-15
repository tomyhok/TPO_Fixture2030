"""Ruta del módulo de estadísticas temporales (CU12)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoPartido
from app.schemas.comunes import PATRON_CODIGO_ISO
from app.schemas.estadisticas import EstadisticasPartido, Resolucion

router = APIRouter(tags=["Estadísticas (InfluxDB)"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/partidos/{codigo_partido}/estadisticas",
    response_model=EstadisticasPartido,
    summary="CU12 - Estadísticas en vivo por ventana temporal",
    description=(
        "Intervalo `[desde, hasta)` en UTC, de 3 horas como máximo, agregado con `date_bin` "
        "a la resolución pedida (10s, 1m o 5m): AVG(posesion_pct), MAX(pases_completados), "
        "MAX(tiros) y MAX(usuarios_activos). Máximo 1.081 puntos por equipo. "
        "Sin puntos en la ventana: 200 con `series: []`."
    ),
    responses=respuestas(503, 504),
)
def estadisticas(
    codigo_partido: CodigoPartido,
    svc: Svc,
    desde: Annotated[datetime, Query(description="Inicio, ISO 8601 con zona.", examples=["2030-06-10T20:00:00Z"])],
    hasta: Annotated[datetime, Query(description="Fin (excluido), ISO 8601 con zona.", examples=["2030-06-10T20:30:00Z"])],
    resolucion: Annotated[Resolucion, Query()] = Resolucion.m1,
    equipo: Annotated[str | None, Query(pattern=PATRON_CODIGO_ISO, description="Filtra un equipo.")] = None,
) -> EstadisticasPartido:
    return svc.estadisticas.consultar(codigo_partido, desde, hasta, resolucion, equipo)

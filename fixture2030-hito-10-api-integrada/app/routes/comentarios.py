"""Lectura por partición de Cassandra; sin escrituras HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import CodigoPartido
from app.schemas.comentarios import MuroComentarios
from app.schemas.comunes import PATRON_UUID

router = APIRouter(tags=["Comentarios (Cassandra)"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/partidos/{codigo_partido}/comentarios",
    response_model=MuroComentarios,
    summary="CU08 - Muro de comentarios de un partido (una ventana de 1 minuto)",
    description=(
        "Lee las 4 particiones `(id_partido, ventana, shard)` de la ventana pedida y las combina "
        "del más reciente al más viejo. Para la página siguiente se envía `cursor` con el valor "
        "de `cursor_siguiente`. Una ventana sin comentarios devuelve `items: []`; no se verifica "
        "que el partido exista en otra fuente."
    ),
    responses=respuestas(503, 504),
)
def muro(
    codigo_partido: CodigoPartido,
    svc: Svc,
    ventana: Annotated[
        str,
        Query(pattern=r"^\d{12}$", description="Minuto AAAAMMDDHHMM (UTC).", examples=["203006152016"]),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(pattern=PATRON_UUID, description="cursor_siguiente.")] = None,
) -> MuroComentarios:
    return svc.comentarios.muro(codigo_partido, ventana, limit, cursor)

"""Rutas del módulo de comentarios (CU08, CU09)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import ClaveIdempotencia, CodigoPartido
from app.schemas.comentarios import Comentario, ComentarioNuevo, MuroComentarios
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


@router.post(
    "/partidos/{codigo_partido}/comentarios",
    response_model=Comentario,
    status_code=status.HTTP_201_CREATED,
    summary="CU09 - Publicar un comentario",
    description=(
        "Escribe en `comentarios_por_partido` y `comentarios_por_usuario` (BATCH logged). "
        "Exige `Idempotency-Key`: repetir la request con la misma clave y el mismo cuerpo "
        "devuelve 200 con el mismo comentario y `Idempotent-Replayed: true`, sin duplicarlo."
    ),
    responses={
        200: {
            "model": Comentario,
            "description": "Repetición con la misma Idempotency-Key: no se volvió a escribir.",
            "headers": {"Idempotent-Replayed": {"schema": {"type": "string", "enum": ["true"]}}},
        },
        **respuestas(404, 409, 503, 504),
    },
)
def publicar(
    codigo_partido: CodigoPartido,
    cuerpo: ComentarioNuevo,
    clave: ClaveIdempotencia,
    response: Response,
    svc: Svc,
) -> Comentario:
    comentario, repetida = svc.comentarios.publicar(codigo_partido, cuerpo, clave)
    if repetida:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    response.headers["Location"] = (
        f"/partidos/{codigo_partido}/comentarios?ventana={comentario.ventana}"
    )
    return comentario

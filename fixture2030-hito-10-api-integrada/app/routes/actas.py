"""Rutas del módulo de entidades complejas (CU13–CU15)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.errores import ConflictoEstado
from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import ClaveIdempotencia, CodigoPartido
from app.schemas.actas import Acta, CambioEstado, EventoNuevo, EventoRegistrado, ResultadoCambioEstado

router = APIRouter(tags=["Actas oficiales (IRIS)"])
Svc = Annotated[Servicios, Depends(servicios)]

_TRANSICION_INVALIDA = ConflictoEstado(
    "No se puede pasar de 'Finalizado' a 'En Juego'. "
    "Transiciones permitidas: Programado -> En Juego -> Finalizado.",
    [{"estado_actual": "Finalizado", "estado_pedido": "En Juego"}],
)


@router.get(
    "/partidos-oficiales/{codigo_partido}",
    response_model=Acta,
    summary="CU13 - Acta oficial de un partido",
    responses=respuestas(404, 503, 504),
)
def obtener_acta(codigo_partido: CodigoPartido, svc: Svc) -> Acta:
    return svc.actas.obtener(codigo_partido)


@router.patch(
    "/partidos-oficiales/{codigo_partido}/estado",
    response_model=ResultadoCambioEstado,
    summary="CU14 - Cambiar el estado del partido",
    description=(
        "Máquina de estados Programado -> En Juego -> Finalizado, validada antes de `%Save()`. "
        "Una transición no permitida responde 409 sin persistir nada. Pedir el estado actual "
        "responde 200 con `cambiado: false` (idempotente)."
    ),
    responses=respuestas(404, 409, 503, 504, ejemplos={409: _TRANSICION_INVALIDA}),
)
def cambiar_estado(codigo_partido: CodigoPartido, cuerpo: CambioEstado, svc: Svc) -> ResultadoCambioEstado:
    return svc.actas.cambiar_estado(codigo_partido, cuerpo.estado)


@router.post(
    "/partidos-oficiales/{codigo_partido}/eventos",
    response_model=EventoRegistrado,
    status_code=status.HTTP_201_CREATED,
    summary="CU15 - Registrar un evento en el acta",
    description=(
        "La regla 'un partido Finalizado no admite eventos' la aplica `Fixture.Evento:%OnBeforeSave` "
        "y se informa como 409. Exige `Idempotency-Key`: un reintento con la misma clave devuelve "
        "200 con el mismo resultado sin duplicar el evento."
    ),
    responses={
        200: {
            "model": EventoRegistrado,
            "description": "Repetición con la misma Idempotency-Key: no se volvió a escribir.",
            "headers": {"Idempotent-Replayed": {"schema": {"type": "string", "enum": ["true"]}}},
        },
        **respuestas(404, 409, 503, 504),
    },
)
def registrar_evento(
    codigo_partido: CodigoPartido,
    cuerpo: EventoNuevo,
    clave: ClaveIdempotencia,
    response: Response,
    svc: Svc,
) -> EventoRegistrado:
    registrado, repetida = svc.actas.registrar_evento(codigo_partido, cuerpo, clave)
    if repetida:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return registrado

"""Rutas del módulo de sesiones (CU10, CU11)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.errores import SesionNoVigente
from app.core.http import respuestas
from app.dependencias import Servicios, servicios
from app.routes.parametros import IdSesion
from app.schemas.sesiones import Sesion

router = APIRouter(tags=["Sesiones (Redis)"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/sesiones/{id_sesion}",
    response_model=Sesion,
    summary="CU10 - Validar una sesión",
    description=(
        "Lee `sesion:<id>` y su TTL. Una sesión inexistente o expirada responde 404 "
        "`SESION_NO_VIGENTE` (Redis borra la clave al expirar, así que ambos casos son iguales). "
        "Redis caído responde 503/504. La lectura no renueva el TTL."
    ),
    responses=respuestas(
        404,
        503,
        504,
        ejemplos={404: SesionNoVigente("No existe una sesión vigente con id 'S-9999'.")},
    ),
)
def obtener_sesion(id_sesion: IdSesion, svc: Svc) -> Sesion:
    return svc.sesiones.obtener(id_sesion)


@router.delete(
    "/sesiones/{id_sesion}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="CU11 - Cerrar (invalidar) una sesión",
    description="`DEL sesion:<id>`. Idempotente: devuelve 204 aunque la sesión ya no exista.",
    responses=respuestas(503, 504),
)
def cerrar_sesion(id_sesion: IdSesion, svc: Svc) -> Response:
    svc.sesiones.cerrar(id_sesion)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

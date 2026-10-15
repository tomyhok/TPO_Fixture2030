"""Ruta de conectividad (CU16)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.dependencias import Servicios, servicios
from app.schemas.salud import Salud

router = APIRouter(tags=["Salud"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/health",
    response_model=Salud,
    summary="CU16 - Disponibilidad de las seis fuentes",
    description=(
        "Ejecuta una operación trivial en cada fuente, en paralelo y con el timeout de cada "
        "adaptador. 200 si todas responden; 503 si al menos una falla, indicando cuál."
    ),
    responses={503: {"model": Salud, "description": "Al menos una fuente no está disponible."}},
)
def health(response: Response, svc: Svc) -> Salud:
    salud = svc.salud.verificar()
    if salud.estado != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return salud

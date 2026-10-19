"""Rutas de salud: chequeo del Hito 10 (CU16) y liveness/readiness/diagnóstico del Hito 11."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencias import Servicios, servicios
from app.schemas.salud import Diagnostico, Preparacion, Salud, Vida

router = APIRouter(tags=["Salud"])
Svc = Annotated[Servicios, Depends(servicios)]


@router.get(
    "/health",
    response_model=Salud,
    summary="CU16 - Disponibilidad de las seis fuentes",
    description=(
        "Ejecuta una operación trivial en cada fuente, en paralelo y con el timeout de cada "
        "adaptador. 200 si todas responden; 503 si al menos una falla, indicando cuál. "
        "Consulta las seis bases en cada llamada: para sondeos frecuentes usar /health/ready."
    ),
    responses={503: {"model": Salud, "description": "Al menos una fuente no está disponible."}},
)
def health(response: Response, svc: Svc) -> Salud:
    salud = svc.salud.verificar()
    if salud.estado != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return salud


@router.get(
    "/health/live",
    response_model=Vida,
    summary="Liveness - el proceso de la API responde",
    description="No consulta ninguna fuente. Si el proceso está colgado o detenido, no hay respuesta.",
)
def vida(response: Response, svc: Svc) -> Vida:
    response.headers["Cache-Control"] = "no-store"
    return svc.salud.vida()


@router.get(
    "/health/ready",
    response_model=Preparacion,
    summary="Readiness - la API puede recibir tráfico",
    description=(
        "Usa el diagnóstico profundo, reutilizado durante HEALTH_CACHE_TTL_S (10 s por defecto). "
        "200 si al menos una fuente está disponible (cada ruta de una fuente caída responde 503/504 "
        "con la dependencia identificada); 503 si ninguna lo está. `no_disponibles` lista las fuentes "
        "afectadas."
    ),
    responses={503: {"model": Preparacion, "description": "Ninguna fuente disponible."}},
)
def preparacion(response: Response, svc: Svc) -> Preparacion:
    resultado = svc.salud.preparacion()
    response.headers["Cache-Control"] = "no-store"
    if not resultado.listo:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return resultado


@router.get(
    "/health/dependencias",
    response_model=Diagnostico,
    summary="Diagnóstico de conectividad por fuente",
    description=(
        "Estado de cada fuente: up, down (caída, rechazo, credencial, contexto o timeout), degraded "
        "(responde más lento que HEALTH_UMBRAL_LENTO_MS), unknown (no se pudo evaluar) o "
        "not_configured (faltan variables; no se consulta). Responde 200 porque el recurso pedido es "
        "el informe: el estado de cada fuente va en el cuerpo. El chequeo se reutiliza durante "
        "HEALTH_CACHE_TTL_S salvo `refrescar=true`."
    ),
)
def dependencias(
    response: Response,
    svc: Svc,
    refrescar: Annotated[bool, Query(description="Ignora el resultado reutilizado y vuelve a consultar.")] = False,
) -> Diagnostico:
    response.headers["Cache-Control"] = "no-store"
    return svc.salud.diagnostico(refrescar)

"""Rutas operativas para consultar logs persistidos en Apache Cassandra.

Quedan fuera del contrato OpenAPI del Hito 10 (`include_in_schema=False`) para no
alterar el contrato público de las 5 lecturas de dominio y salud.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.dependencias import Servicios, servicios
from app.schemas.logs import ListadoLogsHora, ListadoLogsNivel, TrazaLogsRequest

router = APIRouter(prefix="/observabilidad/logs", include_in_schema=False)
Svc = Annotated[Servicios, Depends(servicios)]


@router.get("", response_model=ListadoLogsHora)
def listar_logs_hora(
    svc: Svc,
    ventana_hora: Annotated[str | None, Query(description="Ventana UTC AAAAMMDDHH.")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListadoLogsHora:
    return svc.logs.por_hora(ventana_hora, limit)


@router.get("/request/{request_id}", response_model=TrazaLogsRequest)
def listar_logs_request(
    request_id: Annotated[str, Path(description="X-Request-ID a trazar.")],
    svc: Svc,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TrazaLogsRequest:
    return svc.logs.por_request(request_id, limit)


@router.get("/errores", response_model=ListadoLogsNivel)
def listar_logs_errores(
    svc: Svc,
    nivel: Annotated[str, Query(description="WARNING | ERROR | CRITICAL")] = "ERROR",
    fecha: Annotated[str | None, Query(description="Fecha UTC AAAAMMDD.")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListadoLogsNivel:
    return svc.logs.por_nivel(nivel, fecha, limit)

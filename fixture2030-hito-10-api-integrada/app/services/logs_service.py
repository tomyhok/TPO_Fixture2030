"""Servicio de consulta operativa de logs persistidos en Apache Cassandra."""

import re
from datetime import UTC, datetime
from typing import Any

from app.core.errores import ErrorValidacion
from app.core.logs_cassandra import NIVELES_INCIDENTE
from app.schemas.logs import ListadoLogsHora, ListadoLogsNivel, TrazaLogsRequest

_PATRON_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def validar_ventana_hora(ventana_hora: str | None) -> str:
    if ventana_hora is None:
        return datetime.now(UTC).strftime("%Y%m%d%H")
    if not re.fullmatch(r"\d{10}", ventana_hora):
        raise ErrorValidacion(
            "La ventana horaria debe tener formato AAAAMMDDHH.",
            [{"campo": "query.ventana_hora", "mensaje": "AAAAMMDDHH (10 dígitos UTC)"}],
        )
    try:
        datetime.strptime(ventana_hora, "%Y%m%d%H")
    except ValueError as exc:
        raise ErrorValidacion(
            "La ventana horaria no es válida.",
            [{"campo": "query.ventana_hora", "mensaje": "AAAAMMDDHH"}],
        ) from exc
    return ventana_hora


def validar_fecha(fecha: str | None) -> str:
    if fecha is None:
        return datetime.now(UTC).strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", fecha):
        raise ErrorValidacion(
            "La fecha debe tener formato AAAAMMDD.",
            [{"campo": "query.fecha", "mensaje": "AAAAMMDD (8 dígitos UTC)"}],
        )
    try:
        datetime.strptime(fecha, "%Y%m%d")
    except ValueError as exc:
        raise ErrorValidacion(
            "La fecha no es válida.",
            [{"campo": "query.fecha", "mensaje": "AAAAMMDD"}],
        ) from exc
    return fecha


def validar_nivel(nivel: str) -> str:
    normalizado = nivel.strip().upper()
    if normalizado not in NIVELES_INCIDENTE:
        raise ErrorValidacion(
            "Nivel de incidente inválido; usar WARNING, ERROR o CRITICAL.",
            [{"campo": "query.nivel", "mensaje": "WARNING | ERROR | CRITICAL"}],
        )
    return normalizado


def validar_request_id(request_id: str) -> str:
    if not _PATRON_REQUEST_ID.match(request_id) or request_id == "-":
        raise ErrorValidacion(
            "request_id inválido.",
            [{"campo": "path.request_id", "mensaje": "1..64 caracteres alfanuméricos, '.', '_' o '-'"}],
        )
    return request_id


class LogsService:
    def __init__(self, cassandra: Any, servicio_default: str = "fixture2030-api") -> None:
        self._cassandra = cassandra
        self._servicio_default = servicio_default

    def por_hora(self, ventana_hora: str | None, limit: int, servicio: str | None = None) -> ListadoLogsHora:
        ventana = validar_ventana_hora(ventana_hora)
        svc = servicio or self._servicio_default
        items = self._cassandra.leer_logs_por_hora(svc, ventana, limit)
        return ListadoLogsHora(servicio=svc, ventana_hora=ventana, items=items)

    def por_request(self, request_id: str, limit: int) -> TrazaLogsRequest:
        req_id = validar_request_id(request_id)
        items = self._cassandra.leer_logs_por_request(req_id, limit)
        return TrazaLogsRequest(request_id=req_id, items=items)

    def por_nivel(self, nivel: str, fecha: str | None, limit: int) -> ListadoLogsNivel:
        niv = validar_nivel(nivel)
        fec = validar_fecha(fecha)
        items = self._cassandra.leer_logs_por_nivel(niv, fec, limit)
        return ListadoLogsNivel(nivel=niv, fecha=fec, items=items)

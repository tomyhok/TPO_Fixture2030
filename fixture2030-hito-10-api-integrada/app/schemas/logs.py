"""Esquemas Pydantic para consulta de logs persistidos en Cassandra."""

from datetime import datetime

from pydantic import Field

from app.schemas.comunes import Modelo


class EntradaLog(Modelo):
    id_log: str = Field(description="timeuuid: identidad única y orden temporal del evento.")
    creado_en: datetime
    servicio: str
    nivel: str
    logger: str
    request_id: str
    metodo: str | None = None
    ruta: str | None = None
    status_http: int | None = None
    dependencia: str | None = None
    operacion: str | None = None
    resultado: str | None = None
    duracion_ms: float | None = None
    mensaje: str
    instancia: str


class ListadoLogsHora(Modelo):
    servicio: str
    ventana_hora: str = Field(description="Ventana horaria UTC AAAAMMDDHH.")
    items: list[EntradaLog]


class TrazaLogsRequest(Modelo):
    request_id: str
    items: list[EntradaLog]


class ListadoLogsNivel(Modelo):
    nivel: str
    fecha: str = Field(description="Fecha UTC AAAAMMDD.")
    items: list[EntradaLog]

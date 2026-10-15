"""Contratos del módulo de estadísticas temporales (InfluxDB)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.comunes import Modelo


class Resolucion(StrEnum):
    s10 = "10s"
    m1 = "1m"
    m5 = "5m"


class PuntoEstadistica(Modelo):
    instante: datetime = Field(description="Inicio de la ventana de agregación (UTC).")
    posesion_pct_prom: float = Field(description="AVG(posesion_pct) en la ventana.")
    pases_completados_max: int = Field(description="MAX del contador acumulado = total al cierre.")
    tiros_max: int = Field(description="MAX del contador acumulado = total al cierre.")
    usuarios_activos_max: int = Field(description="Pico de usuarios en la ventana.")


class SerieEquipo(Modelo):
    equipo: str
    puntos: list[PuntoEstadistica]


class EstadisticasPartido(Modelo):
    codigo_partido: str
    desde: datetime
    hasta: datetime
    resolucion: Resolucion
    series: list[SerieEquipo]

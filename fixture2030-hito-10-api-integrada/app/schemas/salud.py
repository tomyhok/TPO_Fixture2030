"""Contrato del chequeo de conectividad."""

from enum import StrEnum

from app.schemas.comunes import Modelo


class EstadoDependencia(StrEnum):
    ok = "ok"
    caida = "caida"
    timeout = "timeout"


class Dependencia(Modelo):
    nombre: str
    estado: EstadoDependencia
    latencia_ms: float


class Salud(Modelo):
    estado: str  # "ok" | "degradado"
    dependencias: list[Dependencia]

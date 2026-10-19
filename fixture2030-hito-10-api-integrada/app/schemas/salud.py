"""Contratos de salud: chequeo del Hito 10 y liveness/readiness/diagnóstico del Hito 11."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.schemas.comunes import Modelo


# ----------------------------------------------------------- Hito 10 (/health)
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


# ------------------------------------------------- Hito 11 (/health/live, ...)
class EstadoComponente(StrEnum):
    """Significado fijo de cada estado (Hito 11, sección 5.6)."""

    up = "up"  # la prueba configurada terminó correctamente
    down = "down"  # se intentó la prueba y falló (caída, rechazo, credencial, contexto o timeout)
    degraded = "degraded"  # responde, pero más lento que el umbral; en el global: alguna fuente afectada
    unknown = "unknown"  # no se pudo evaluar (error inesperado del chequeo)
    not_configured = "not_configured"  # faltan variables imprescindibles: no se consulta


class Vida(Modelo):
    estado: Literal["up"] = Field(description="Siempre `up`: si el proceso no responde, no hay respuesta.")
    version: str
    activa_desde_s: float = Field(description="Segundos desde que arrancó el proceso.")


class DiagnosticoDependencia(Modelo):
    nombre: str
    estado: EstadoComponente
    motivo: str | None = Field(
        None,
        description=(
            "Código del problema: DEPENDENCIA_NO_DISPONIBLE, DEPENDENCIA_TIMEOUT, LATENCIA_ALTA, "
            "FALTA_CONFIGURACION:<variables> o ERROR_INESPERADO. Nunca incluye hosts ni credenciales."
        ),
    )
    latencia_ms: float | None = Field(None, description="Duración del chequeo; null si no se ejecutó.")


class Diagnostico(Modelo):
    estado: EstadoComponente = Field(description="`up`, `degraded` (alguna fuente afectada) o `down` (ninguna disponible).")
    verificado_en: datetime = Field(description="Instante (UTC) del chequeo profundo que se informa.")
    desde_cache: bool = Field(description="true si se reutilizó un chequeo previo dentro del TTL.")
    edad_s: float = Field(description="Antigüedad del chequeo informado.")
    ttl_cache_s: float
    dependencias: list[DiagnosticoDependencia]


class Preparacion(Modelo):
    listo: bool = Field(description="true si la API puede atender tráfico (al menos una fuente disponible).")
    estado: EstadoComponente
    disponibles: list[str]
    no_disponibles: list[str]
    verificado_en: datetime
    desde_cache: bool

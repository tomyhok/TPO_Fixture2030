"""Modelos compartidos: formato de error único y patrones de parámetros."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Formatos de identificadores de negocio, homologados entre los módulos del TPO.
PATRON_CODIGO_ISO = r"^[A-Z]{3}$"
PATRON_ID_JUGADOR = r"^[A-Z]{3}-\d{1,2}$"
PATRON_CODIGO_PARTIDO = r"^P-\d{3}$"
PATRON_ID_SESION = r"^S-\d{4,}$"
PATRON_UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorCuerpo(Modelo):
    codigo: str = Field(description="Tipo de problema, estable para el consumidor.")
    mensaje: str = Field(description="Descripción apta para el consumidor, sin detalle técnico.")
    request_id: str = Field(description="Identificador para correlacionar con los logs.")
    detalles: list[dict[str, Any]] = Field(default_factory=list)


class ErrorRespuesta(Modelo):
    error: ErrorCuerpo

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "codigo": "RECURSO_NO_ENCONTRADO",
                    "mensaje": "No existe la selección 'XYZ'.",
                    "request_id": "7f3c1a2e-0b4d-4c55-9a51-2f0f3c9e8d10",
                    "detalles": [],
                }
            }
        }
    )

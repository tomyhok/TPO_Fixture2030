"""Contratos del módulo de entidades complejas (IRIS)."""

from datetime import date
from enum import StrEnum

from pydantic import ConfigDict, Field

from app.schemas.comunes import Modelo


class EstadoPartido(StrEnum):
    programado = "Programado"
    en_juego = "En Juego"
    finalizado = "Finalizado"


class TipoEvento(StrEnum):
    gol = "Gol"
    amarilla = "Tarjeta Amarilla"
    roja = "Tarjeta Roja"
    cambio = "Cambio"


class Arbitro(Modelo):
    nombre: str
    apellido: str
    rango: str


class EventoActa(Modelo):
    minuto: int
    tipo: str
    descripcion: str | None = None


class Acta(Modelo):
    codigo_partido: str
    sede: str
    fecha: date
    estado: EstadoPartido
    arbitro: Arbitro
    eventos: list[EventoActa]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_partido": "P-001",
                "sede": "Estadio Monumental",
                "fecha": "2030-06-10",
                "estado": "En Juego",
                "arbitro": {"nombre": "Facundo", "apellido": "Tello", "rango": "FIFA"},
                "eventos": [{"minuto": 23, "tipo": "Gol", "descripcion": "Gol de ARG-10"}],
            }
        }
    )


class CambioEstado(Modelo):
    estado: EstadoPartido


class ResultadoCambioEstado(Modelo):
    cambiado: bool = Field(description="false si el partido ya estaba en el estado pedido (idempotente).")
    acta: Acta


class EventoNuevo(Modelo):
    minuto: int = Field(ge=1, le=130)
    tipo: TipoEvento
    descripcion: str = Field(default="", max_length=200)

    model_config = ConfigDict(
        json_schema_extra={"example": {"minuto": 67, "tipo": "Gol", "descripcion": "Gol de ARG-9"}}
    )


class EventoRegistrado(Modelo):
    codigo_partido: str
    evento: EventoActa
    acta: Acta

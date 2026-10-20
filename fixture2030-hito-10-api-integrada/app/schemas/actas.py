"""Contratos del módulo de entidades complejas (IRIS)."""

from datetime import date
from enum import StrEnum

from pydantic import ConfigDict

from app.schemas.comunes import Modelo


class EstadoPartido(StrEnum):
    programado = "Programado"
    en_juego = "En Juego"
    finalizado = "Finalizado"


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

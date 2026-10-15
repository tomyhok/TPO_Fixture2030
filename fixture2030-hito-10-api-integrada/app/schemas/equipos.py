"""Contratos del módulo documental (MongoDB)."""

from datetime import date
from enum import StrEnum

from pydantic import ConfigDict, Field

from app.schemas.comunes import Modelo


class Confederacion(StrEnum):
    CONMEBOL = "CONMEBOL"
    UEFA = "UEFA"
    CAF = "CAF"
    AFC = "AFC"
    CONCACAF = "CONCACAF"
    OFC = "OFC"


class Grupo(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"  # noqa: E741 - nombre del grupo
    J = "J"
    K = "K"
    L = "L"
    M = "M"
    N = "N"
    O = "O"  # noqa: E741 - nombre del grupo
    P = "P"


class Posicion(StrEnum):
    ARQ = "ARQ"
    DEF = "DEF"
    MED = "MED"
    DEL = "DEL"


class EquipoResumen(Modelo):
    codigo_iso: str
    nombre: str
    confederacion: str
    grupo: str
    ranking_fifa: int


class EquipoDetalle(EquipoResumen):
    director_tecnico: str | None = None
    pais_anfitrion: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_iso": "ARG",
                "nombre": "Argentina",
                "confederacion": "CONMEBOL",
                "grupo": "A",
                "ranking_fifa": 1,
                "director_tecnico": "Martinez",
                "pais_anfitrion": True,
            }
        }
    )


class PaginaEquipos(Modelo):
    items: list[EquipoResumen]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)


class JugadorResumen(Modelo):
    id_jugador: str
    nombre: str
    dorsal: int
    posicion: str
    club_actual: str


class JugadorDetalle(JugadorResumen):
    fecha_nacimiento: date
    edad: int
    altura_cm: int
    pie_habil: str
    codigo_equipo: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_jugador": "ARG-10",
                "nombre": "Andrés Fuentes",
                "dorsal": 10,
                "posicion": "DEF",
                "club_actual": "No informado",
                "fecha_nacimiento": "2004-10-18",
                "edad": 25,
                "altura_cm": 179,
                "pie_habil": "izquierdo",
                "codigo_equipo": "ARG",
            }
        }
    )


class PaginaJugadores(Modelo):
    codigo_iso: str
    items: list[JugadorResumen]
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)

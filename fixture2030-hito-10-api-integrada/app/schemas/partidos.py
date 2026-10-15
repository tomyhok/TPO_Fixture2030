"""Contratos del módulo de grafos (Neo4j) y de la caché de partidos (Redis)."""

from datetime import date

from pydantic import ConfigDict

from app.schemas.comunes import Modelo


class EquipoEnPartido(Modelo):
    codigo_iso: str
    nombre: str


class Sede(Modelo):
    codigo_sede: str
    nombre: str
    ciudad: str


class FichaPartido(Modelo):
    codigo_partido: str
    fecha: date | None = None
    fase: str | None = None
    local: EquipoEnPartido | None = None
    visitante: EquipoEnPartido | None = None
    sede: Sede | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_partido": "P-001",
                "fecha": "2030-06-10",
                "fase": "Grupos",
                "local": {"codigo_iso": "ARG", "nombre": "Argentina"},
                "visitante": {"codigo_iso": "ESP", "nombre": "Espana"},
                "sede": {"codigo_sede": "MON", "nombre": "Estadio Monumental", "ciudad": "Buenos Aires"},
            }
        }
    )


class Protagonista(Modelo):
    id_jugador: str
    nombre: str


class EventoGrafo(Modelo):
    id_evento: str
    tipo: str
    minuto: int
    jugador: Protagonista | None = None


class EventosPartido(Modelo):
    codigo_partido: str
    eventos: list[EventoGrafo]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "codigo_partido": "P-001",
                "eventos": [
                    {
                        "id_evento": "EV-001",
                        "tipo": "Gol",
                        "minuto": 23,
                        "jugador": {"id_jugador": "ARG-10", "nombre": "Andrés Fuentes"},
                    }
                ],
            }
        }
    )


class Rival(Modelo):
    codigo_iso: str
    nombre: str
    codigo_partido: str
    fecha: date | None = None
    condicion: str | None = None


class RivalesEquipo(Modelo):
    codigo_iso: str
    rivales: list[Rival]

from pydantic import ConfigDict
from app.schemas.comunes import Modelo

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

"""Vista documental acotada a una selección."""
from app.schemas.comunes import Modelo
class EquipoDetalle(Modelo):
    codigo_iso: str
    nombre: str
    confederacion: str
    grupo: str
    ranking_fifa: int
    director_tecnico: str | None = None
    pais_anfitrion: bool

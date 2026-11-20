"""Contratos del portal de demostración (/portal/api). Fuera del contrato OpenAPI del Hito 10."""

from pydantic import Field

from app.schemas.comentarios import Comentario
from app.schemas.comunes import PATRON_CODIGO_ISO, PATRON_ID_JUGADOR, Modelo
from app.schemas.equipos import EquipoDetalle


class EquipoEnPartido(Modelo):
    codigo_iso: str
    nombre: str | None = None
    condicion: str | None = None


class Sede(Modelo):
    nombre: str
    ciudad: str | None = None


class PartidoFixture(Modelo):
    codigo_partido: str
    fecha: str | None
    fase: str | None
    sede: Sede | None
    equipos: list[EquipoEnPartido]


class Jugador(Modelo):
    id_jugador: str
    nombre: str
    dorsal: int | None = None
    posicion: str | None = None
    edad: int | None = None
    club_actual: str | None = None


class Plantel(Modelo):
    equipo: EquipoDetalle
    jugadores: list[Jugador]


class NuevaSesion(Modelo):
    alias: str = Field(min_length=3, max_length=24, pattern=r"^[\w .-]+$")
    equipo_favorito: str | None = Field(None, pattern=PATRON_CODIGO_ISO)


class SesionPortal(Modelo):
    id_sesion: str
    usuario_id: str
    alias: str
    rol: str | None = None
    estado: str | None = None
    equipo_favorito: str | None = None
    ttl_restante_s: int | None


class NuevoComentario(Modelo):
    texto: str = Field(min_length=1, max_length=280)
    equipo_apoyado: str = Field(pattern=PATRON_CODIGO_ISO)
    minuto_partido: int | None = Field(None, ge=0, le=130)


class MuroPortal(Modelo):
    codigo_partido: str
    ventanas: list[str] = Field(description="Ventanas de 1 minuto leídas (AAAAMMDDHHMM, UTC).")
    items: list[Comentario]


class Voto(Modelo):
    id_jugador: str = Field(pattern=PATRON_ID_JUGADOR)


class VotoFigura(Modelo):
    id_jugador: str
    votos: int


class EstadoVivo(Modelo):
    codigo_partido: str
    visitas: int
    conectados: int
    encuesta: list[VotoFigura]
    ya_voto: bool

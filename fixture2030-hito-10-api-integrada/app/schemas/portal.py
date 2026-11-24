"""Contratos del portal de demostración (/portal/api). Fuera del contrato OpenAPI del Hito 10."""

from enum import StrEnum

from pydantic import Field

from app.schemas.comentarios import Comentario
from app.schemas.comunes import PATRON_CODIGO_ISO, Modelo
from app.schemas.equipos import EquipoDetalle


class EquipoEnPartido(Modelo):
    codigo_iso: str
    nombre: str | None = None
    condicion: str | None = None


class Sede(Modelo):
    nombre: str
    ciudad: str | None = None


class EstadoPartido(StrEnum):
    programado = "Programado"
    en_juego = "En Juego"
    finalizado = "Finalizado"


# Solo se avanza: Programado -> En Juego -> Finalizado (se puede saltear En Juego).
ORDEN_ESTADOS = [EstadoPartido.programado, EstadoPartido.en_juego, EstadoPartido.finalizado]


class Arbitro(Modelo):
    nombre: str
    apellido: str
    rango: str | None = None


class PartidoFixture(Modelo):
    codigo_partido: str
    fecha: str | None
    fase: str | None
    grupo: str | None = Field(None, description="Letra del grupo (fase de grupos).")
    jornada: int | None = Field(None, description="Fecha 1, 2 o 3 de la fase de grupos.")
    estado: EstadoPartido
    inicio: str | None = Field(None, description="Hora real (UTC) en que arrancó el partido simulado.")
    sede: Sede | None
    arbitro: Arbitro | None = None
    equipos: list[EquipoEnPartido]
    goles: dict[str, int] = Field(default_factory=dict, description="Goles por selección (eventos Gol de Neo4j).")


class NuevoEstado(Modelo):
    estado: EstadoPartido


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
    """El minuto del partido lo pone la API con el reloj de la simulación (Redis)."""

    texto: str = Field(min_length=1, max_length=280)
    equipo_apoyado: str = Field(pattern=PATRON_CODIGO_ISO)


class MuroPortal(Modelo):
    codigo_partido: str
    ventanas: list[str] = Field(description="Ventanas de 1 minuto leídas (AAAAMMDDHHMM, UTC).")
    items: list[Comentario]


class Reloj(Modelo):
    minuto: int = Field(description="Minuto de juego (después del 90 se muestra 90+n).")
    adicion: int = Field(description="Minutos de descuento sorteados para el final.")
    en_curso: bool = Field(description="La simulación sigue corriendo.")


class EstadoVivo(Modelo):
    codigo_partido: str
    visitas: int
    conectados: int
    reloj: Reloj | None = Field(None, description="Reloj del partido simulado (Redis); null si no hay simulación.")

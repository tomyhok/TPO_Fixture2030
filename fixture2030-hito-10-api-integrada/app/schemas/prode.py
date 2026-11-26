"""Contratos del prode del portal (/portal/api). Fuera del contrato OpenAPI del Hito 10."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.comunes import Modelo


class NuevaPrediccion(Modelo):
    goles_local: int = Field(ge=0, le=20)
    goles_visitante: int = Field(ge=0, le=20)


class Marcador(Modelo):
    goles_local: int
    goles_visitante: int


class Prediccion(Modelo):
    codigo_partido: str
    usuario_id: str
    fase: str | None = None
    equipo_local: str
    equipo_visitante: str
    goles_local: int
    goles_visitante: int
    resultado: Literal["L", "E", "V"] = Field(description="L gana el local, E empate, V gana el visitante.")
    puntos: int | None = Field(None, description="Null hasta que el partido se puntúa.")
    acierto: Literal["exacto", "resultado", "ninguno"] | None = None
    resultado_real: Marcador | None = None
    creada_en: datetime
    actualizada_en: datetime


class MarcadorElegido(Marcador):
    cantidad: int


class ResumenPredicciones(Modelo):
    codigo_partido: str
    estado: str = Field(description="Estado del partido en Neo4j: Programado, En Juego o Finalizado.")
    abierta: bool = Field(description="Se puede pronosticar: el partido no empezó ni se puntuó.")
    total: int
    local: int
    empate: int
    visitante: int
    promedio_goles_local: float | None
    promedio_goles_visitante: float | None
    marcadores: list[MarcadorElegido]
    mi_prediccion: Prediccion | None
    resultado_real: Marcador | None = Field(description="Marcador con el que se puntuó, si ya se liquidó.")


class FilaPosicion(Modelo):
    posicion: int
    usuario_id: str
    alias: str
    equipo_favorito: str | None
    puntos: int
    exactos: int
    aciertos: int
    pronosticos: int
    puntuados: int


class TablaPosiciones(Modelo):
    equipo: str | None = Field(description="Hinchada filtrada (selección favorita) o null para la general.")
    total_participantes: int
    filas: list[FilaPosicion]
    mi_fila: FilaPosicion | None
    puntos_exacto: int
    puntos_resultado: int
    pendientes: list[str] = Field(
        description="Partidos con predicciones pendientes que no se pudieron verificar porque Neo4j no respondió.")

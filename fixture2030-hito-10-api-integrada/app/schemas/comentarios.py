"""Contratos del módulo de comentarios (Cassandra)."""

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict, Field

from app.schemas.comunes import PATRON_CODIGO_ISO, Modelo


class Idioma(StrEnum):
    es = "es"
    pt = "pt"
    en = "en"


class ComentarioNuevo(Modelo):
    """Cuerpo de POST /partidos/{codigo_partido}/comentarios. Campos extra: 400."""

    id_usuario: str = Field(pattern=r"^U-\d{4,}$", examples=["U-1001"])
    usuario_alias: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.]+$")
    equipo_apoyado: str = Field(pattern=PATRON_CODIGO_ISO)
    texto: str = Field(min_length=1, max_length=500)
    idioma: Idioma
    minuto_partido: int = Field(ge=0, le=130)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_usuario": "U-1001",
                "usuario_alias": "hincha_albiceleste",
                "equipo_apoyado": "ARG",
                "texto": "Que golazo, se viene la remontada",
                "idioma": "es",
                "minuto_partido": 67,
            }
        }
    )


class Comentario(Modelo):
    id_comentario: str = Field(description="timeuuid: identidad y orden temporal del comentario.")
    codigo_partido: str
    ventana: str = Field(description="Bucket de 1 minuto AAAAMMDDHHMM (parte de la clave de partición).")
    id_usuario: str
    usuario_alias: str | None = None
    equipo_apoyado: str | None = None
    texto: str
    idioma: str | None = None
    estado_moderacion: str
    minuto_partido: int | None = None
    creado_en: datetime


class MuroComentarios(Modelo):
    codigo_partido: str
    ventana: str
    items: list[Comentario]
    cursor_siguiente: str | None = Field(
        description="id_comentario del último elemento; null si no hay más en la ventana."
    )

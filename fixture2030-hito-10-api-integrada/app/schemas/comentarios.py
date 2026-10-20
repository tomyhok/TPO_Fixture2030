from datetime import datetime
from pydantic import Field
from app.schemas.comunes import Modelo

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

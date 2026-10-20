"""Lectura limitada de comentarios según el patrón del Hito 6."""

import uuid
from datetime import datetime
from typing import Any

from app.core.errores import ErrorValidacion
from app.schemas.comentarios import MuroComentarios


def validar_ventana(ventana: str) -> None:
    """El formato ya lo controla la ruta; acá se rechazan fechas imposibles (203013...)."""
    try:
        datetime.strptime(ventana, "%Y%m%d%H%M")
    except ValueError as exc:
        raise ErrorValidacion(
            "La ventana no es una fecha válida.", [{"campo": "query.ventana", "mensaje": "AAAAMMDDHHMM"}]
        ) from exc


def validar_cursor(cursor: str | None) -> uuid.UUID | None:
    if cursor is None:
        return None
    valor = uuid.UUID(cursor)
    if valor.version != 1:
        raise ErrorValidacion(
            "El cursor debe ser un id_comentario (timeuuid).",
            [{"campo": "query.cursor", "mensaje": "timeuuid (UUID v1)"}],
        )
    return valor


class ComentariosService:
    def __init__(self, cassandra: Any):
        self._cassandra = cassandra

    def muro(self, codigo: str, ventana: str, limit: int, cursor: str | None) -> MuroComentarios:
        validar_ventana(ventana)
        desde = validar_cursor(cursor)
        items, hay_mas = self._cassandra.leer_muro(codigo, ventana, limit, desde)
        return MuroComentarios(
            codigo_partido=codigo,
            ventana=ventana,
            items=items,
            cursor_siguiente=items[-1]["id_comentario"] if hay_mas and items else None,
        )

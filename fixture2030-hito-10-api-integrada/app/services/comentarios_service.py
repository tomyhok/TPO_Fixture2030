"""Casos de uso CU08 (muro por partición) y CU09 (publicar comentario)."""

import uuid
import zlib
from datetime import UTC, datetime
from typing import Any

from app.adapters.cassandra_adapter import SHARDS, nuevo_timeuuid
from app.core.errores import ErrorValidacion, RecursoNoEncontrado
from app.schemas.comentarios import Comentario, ComentarioNuevo, MuroComentarios
from app.services.idempotencia import Idempotencia


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
    def __init__(self, cassandra: Any, neo4j: Any, idempotencia: Idempotencia):
        self._cassandra = cassandra
        self._neo4j = neo4j
        self._idempotencia = idempotencia

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

    def publicar(
        self, codigo: str, nuevo: ComentarioNuevo, clave_idempotencia: str
    ) -> tuple[Comentario, bool]:
        cuerpo = {"codigo_partido": codigo, **nuevo.model_dump(mode="json")}

        def escribir() -> dict[str, Any]:
            if not self._neo4j.existe_partido(codigo):
                raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")
            # Cassandra guarda timestamps con precisión de milisegundos.
            ahora = datetime.now(UTC)
            ahora = ahora.replace(microsecond=ahora.microsecond // 1000 * 1000)
            comentario = {
                "codigo_partido": codigo,
                "ventana": ahora.strftime("%Y%m%d%H%M"),
                "shard": zlib.crc32(nuevo.id_usuario.encode("utf-8")) % SHARDS,
                "periodo": ahora.strftime("%Y%m"),
                "id_comentario": nuevo_timeuuid(ahora),
                "id_usuario": nuevo.id_usuario,
                "usuario_alias": nuevo.usuario_alias,
                "equipo_apoyado": nuevo.equipo_apoyado,
                "texto": nuevo.texto,
                "idioma": nuevo.idioma.value,
                "estado_moderacion": "publicado",
                "minuto_partido": nuevo.minuto_partido,
                "creado_en": ahora,
            }
            self._cassandra.publicar(comentario)
            publico = {k: v for k, v in comentario.items() if k not in ("shard", "periodo")}
            publico["id_comentario"] = str(publico["id_comentario"])
            return Comentario.model_validate(publico).model_dump(mode="json")

        respuesta, repetida = self._idempotencia.ejecutar("comentario", clave_idempotencia, cuerpo, escribir)
        return Comentario.model_validate(respuesta), repetida

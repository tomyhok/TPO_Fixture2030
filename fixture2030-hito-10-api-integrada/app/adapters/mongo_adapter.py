"""Adaptador documental: MongoDB (Hito 4, colecciones `equipos` y `jugadores`).

Encapsula el driver pymongo: conexión, selección de la database configurada,
consultas con proyección explícita, paginación y traducción de errores. Las
consultas son las mismas que el Hito 4 indexó (`idx_ranking`,
`idx_confederacion`, `idx_grupo`, `idx_equipo_posicion`); no se aceptan
filtros libres del consumidor.
"""

from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo import errors as mongo_errors

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI

DEPENDENCIA = "mongodb"

PROYECCION_EQUIPO_DETALLE = {
    "_id": 0,
    "codigo_iso": 1,
    "nombre": 1,
    "confederacion": 1,
    "grupo": 1,
    "ranking_fifa": 1,
    "director_tecnico": 1,
    "pais_anfitrion": 1,
}
PROYECCION_EQUIPO_RESUMEN = {
    "_id": 0,
    "codigo_iso": 1,
    "nombre": 1,
    "confederacion": 1,
    "grupo": 1,
    "ranking_fifa": 1,
}
PROYECCION_JUGADOR_RESUMEN = {"_id": 1, "nombre": 1, "dorsal": 1, "posicion": 1, "club_actual": 1}
PROYECCION_JUGADOR_DETALLE = {
    "_id": 1,
    "nombre": 1,
    "dorsal": 1,
    "posicion": 1,
    "fecha_nacimiento": 1,
    "edad": 1,
    "altura_cm": 1,
    "pie_habil": 1,
    "club_actual": 1,
    "codigo_equipo": 1,
}


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, (mongo_errors.NetworkTimeout, mongo_errors.ExecutionTimeout)):
        return timeout(DEPENDENCIA)
    if isinstance(exc, (mongo_errors.ConnectionFailure, mongo_errors.OperationFailure)):
        # Servidor inaccesible, sin primario o credenciales rechazadas.
        return no_disponible(DEPENDENCIA)
    return None


def _jugador(doc: dict[str, Any]) -> dict[str, Any]:
    doc["id_jugador"] = doc.pop("_id")
    return doc


class MongoAdapter:
    def __init__(self, settings: Settings):
        # MongoClient no abre la conexión hasta la primera operación, así que la
        # API arranca aunque MongoDB esté caído.
        self._cliente = MongoClient(
            host=settings.mongo_host,
            port=settings.mongo_port,
            username=settings.mongo_user or None,
            password=settings.mongo_password.get_secret_value() or None,
            authSource=settings.mongo_auth_db,
            serverSelectionTimeoutMS=int(settings.timeout_conexion_s * 1000),
            connectTimeoutMS=int(settings.timeout_conexion_s * 1000),
            socketTimeoutMS=int(settings.timeout_operacion_s * 1000),
            appname="fixture2030-api",
        )
        self._db = self._cliente[settings.mongo_database]

    # ---------------------------------------------------------------- equipos
    def obtener_equipo(self, codigo_iso: str) -> dict[str, Any] | None:
        with operacion(DEPENDENCIA, "equipos.find_one", _traducir):
            return self._db.equipos.find_one({"_id": codigo_iso}, PROYECCION_EQUIPO_DETALLE)

    def existe_equipo(self, codigo_iso: str) -> bool:
        with operacion(DEPENDENCIA, "equipos.exists", _traducir):
            return self._db.equipos.find_one({"_id": codigo_iso}, {"_id": 1}) is not None

    def listar_equipos(
        self, confederacion: str | None, grupo: str | None, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        filtro: dict[str, Any] = {}
        if confederacion:
            filtro["confederacion"] = confederacion
        if grupo:
            filtro["grupo"] = grupo
        with operacion(DEPENDENCIA, "equipos.find_paginado", _traducir):
            total = self._db.equipos.count_documents(filtro)
            cursor = (
                self._db.equipos.find(filtro, PROYECCION_EQUIPO_RESUMEN)
                .sort([("ranking_fifa", ASCENDING), ("_id", ASCENDING)])
                .skip((page - 1) * size)
                .limit(size)
            )
            return list(cursor), total

    # -------------------------------------------------------------- jugadores
    def listar_jugadores(
        self, codigo_equipo: str, posicion: str | None, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        filtro: dict[str, Any] = {"codigo_equipo": codigo_equipo}
        if posicion:
            filtro["posicion"] = posicion
        with operacion(DEPENDENCIA, "jugadores.find_paginado", _traducir):
            total = self._db.jugadores.count_documents(filtro)
            cursor = (
                self._db.jugadores.find(filtro, PROYECCION_JUGADOR_RESUMEN)
                .sort([("dorsal", ASCENDING)])
                .skip((page - 1) * size)
                .limit(size)
            )
            return [_jugador(d) for d in cursor], total

    def obtener_jugador(self, id_jugador: str) -> dict[str, Any] | None:
        with operacion(DEPENDENCIA, "jugadores.find_one", _traducir):
            doc = self._db.jugadores.find_one({"_id": id_jugador}, PROYECCION_JUGADOR_DETALLE)
        return _jugador(doc) if doc else None

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._cliente.admin.command("ping")

    def cerrar(self) -> None:
        self._cliente.close()

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
# Colecciones del Hito 4 que la API necesita: MongoDB no informa error ante una
# database inexistente (la crea al escribir), así que el chequeo de salud las busca.
COLECCIONES = ("equipos", "jugadores")

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


class _ContextoIncompleto(Exception):
    """La database configurada no tiene las colecciones del módulo (nombre incorrecto o sin carga)."""


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, (mongo_errors.NetworkTimeout, mongo_errors.ExecutionTimeout)):
        return timeout(DEPENDENCIA)
    if isinstance(exc, _ContextoIncompleto):
        return no_disponible(DEPENDENCIA)
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
        self._contexto_verificado = False

    def _verificar_contexto(self) -> None:
        """Hito 11: con MONGO_DATABASE incorrecta, MongoDB devuelve vacío sin error y la
        API respondía 404 ("no existe la selección"): una ausencia falsa. La primera
        operación verifica una sola vez que estén las colecciones del módulo; si faltan,
        la fuente queda no disponible (503). Después no tiene costo."""
        if self._contexto_verificado:
            return
        presentes = self._db.list_collection_names(filter={"name": {"$in": list(COLECCIONES)}})
        if set(presentes) != set(COLECCIONES):
            raise _ContextoIncompleto(f"faltan {sorted(set(COLECCIONES) - set(presentes))}")
        self._contexto_verificado = True

    # ---------------------------------------------------------------- equipos
    def obtener_equipo(self, codigo_iso: str) -> dict[str, Any] | None:
        with operacion(DEPENDENCIA, "equipos.find_one", _traducir):
            self._verificar_contexto()
            return self._db.equipos.find_one({"_id": codigo_iso}, PROYECCION_EQUIPO_DETALLE)

    def existe_equipo(self, codigo_iso: str) -> bool:
        with operacion(DEPENDENCIA, "equipos.exists", _traducir):
            self._verificar_contexto()
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
            self._verificar_contexto()
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
            self._verificar_contexto()
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
            self._verificar_contexto()
            doc = self._db.jugadores.find_one({"_id": id_jugador}, PROYECCION_JUGADOR_DETALLE)
        return _jugador(doc) if doc else None

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        """Conexión, autenticación, permiso de listado y contexto en una sola llamada liviana."""
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._contexto_verificado = False  # el chequeo de salud siempre vuelve a verificar
            self._verificar_contexto()

    def cerrar(self) -> None:
        self._cliente.close()

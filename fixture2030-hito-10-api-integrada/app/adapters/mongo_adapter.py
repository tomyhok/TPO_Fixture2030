"""Lectura de una selección y verificación del contexto documental del Hito 4."""

from typing import Any

from pymongo import MongoClient
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




    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        """Conexión, autenticación, permiso de listado y contexto en una sola llamada liviana."""
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._contexto_verificado = False  # el chequeo de salud siempre vuelve a verificar
            self._verificar_contexto()

    def cerrar(self) -> None:
        self._cliente.close()

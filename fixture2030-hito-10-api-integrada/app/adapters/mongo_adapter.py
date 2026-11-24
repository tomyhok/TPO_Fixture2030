"""MongoDB: selecciones y planteles del Hito 4 y el prode del portal.

El prode (predicciones de resultados, puntajes y tabla de posiciones) vive en cuatro
colecciones propias del portal, creadas con validación $jsonSchema e índices la
primera vez que se usan: usuarios_portal, predicciones, liquidaciones y tabla_posiciones.
"""

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
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

# ------------------------------------------------------------------- prode
# Validación en el motor, igual que equipos y jugadores en el Hito 4: un script o
# cliente erróneo no puede guardar un marcador negativo ni un resultado inválido.
_FECHA = {"bsonType": "date"}
_FECHA_O_NULO = {"bsonType": ["date", "null"]}
_GOLES = {"bsonType": "int", "minimum": 0, "maximum": 20}
_ISO = {"bsonType": "string", "pattern": r"^[A-Z]{3}$"}
ESQUEMAS_PRODE: dict[str, dict[str, Any]] = {
    # _id = alias en minúsculas: el mismo alias recupera el mismo usuario_id en cada ingreso.
    "usuarios_portal": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "alias", "creado_en", "ultimo_ingreso"],
        "properties": {
            "_id": {"bsonType": "string", "minLength": 3, "maxLength": 24},
            "usuario_id": {"bsonType": "string", "pattern": r"^U-\d+$"},
            "alias": {"bsonType": "string", "minLength": 3, "maxLength": 24},
            "equipo_favorito": {"bsonType": ["string", "null"], "pattern": r"^[A-Z]{3}$"},
            "creado_en": _FECHA,
            "ultimo_ingreso": _FECHA,
        },
    },
    # _id = "<codigo_partido>:<usuario_id>": una predicción por usuario y partido.
    "predicciones": {
        "bsonType": "object",
        "required": ["_id", "codigo_partido", "usuario_id", "equipo_local", "equipo_visitante",
                     "goles_local", "goles_visitante", "resultado", "creada_en", "actualizada_en"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": r"^P-\d{3}:U-\d+$"},
            "codigo_partido": {"bsonType": "string", "pattern": r"^P-\d{3}$"},
            "usuario_id": {"bsonType": "string", "pattern": r"^U-\d+$"},
            "fase": {"bsonType": ["string", "null"]},
            "equipo_local": _ISO,
            "equipo_visitante": _ISO,
            "goles_local": _GOLES,
            "goles_visitante": _GOLES,
            "resultado": {"enum": ["L", "E", "V"]},
            "puntos": {"bsonType": ["int", "null"], "minimum": 0},
            "acierto": {"enum": ["exacto", "resultado", "ninguno", None]},
            "resultado_real": {
                "bsonType": ["object", "null"],
                "required": ["goles_local", "goles_visitante"],
                "properties": {"goles_local": _GOLES, "goles_visitante": _GOLES},
            },
            "creada_en": _FECHA,
            "actualizada_en": _FECHA,
            "liquidada_en": _FECHA_O_NULO,
        },
    },
    # _id = codigo_partido: el resultado con el que se puntuó cada partido.
    "liquidaciones": {
        "bsonType": "object",
        "required": ["_id", "goles_local", "goles_visitante", "predicciones_puntuadas", "liquidado_en"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": r"^P-\d{3}$"},
            "goles_local": _GOLES,
            "goles_visitante": _GOLES,
            "predicciones_puntuadas": {"bsonType": "int", "minimum": 0},
            "liquidado_en": _FECHA,
        },
    },
    # _id = usuario_id: vista materializada con $merge desde predicciones.
    "tabla_posiciones": {
        "bsonType": "object",
        "required": ["_id", "alias", "puntos", "exactos", "aciertos", "pronosticos", "puntuados", "orden"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": r"^U-\d+$"},
            "alias": {"bsonType": "string"},
            "equipo_favorito": {"bsonType": ["string", "null"]},
            "puntos": {"bsonType": ["int", "long"], "minimum": 0},
            "exactos": {"bsonType": ["int", "long"], "minimum": 0},
            "aciertos": {"bsonType": ["int", "long"], "minimum": 0},
            "pronosticos": {"bsonType": ["int", "long"], "minimum": 0},
            "puntuados": {"bsonType": ["int", "long"], "minimum": 0},
            "orden": {"bsonType": ["int", "long"]},
        },
    },
}
INDICES_PRODE: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
    "usuarios_portal": [([("usuario_id", ASCENDING)], {"name": "idx_usuario_id_unico", "unique": True})],
    "predicciones": [
        # "Mis predicciones": todas las de un usuario, ordenadas por partido.
        ([("usuario_id", ASCENDING), ("codigo_partido", ASCENDING)], {"name": "idx_usuario_partido"}),
        # Resumen de un partido y búsqueda de las que faltan puntuar.
        ([("codigo_partido", ASCENDING), ("puntos", ASCENDING)], {"name": "idx_partido_puntos"}),
    ],
    "tabla_posiciones": [
        ([("orden", DESCENDING)], {"name": "idx_orden"}),
        ([("equipo_favorito", ASCENDING), ("orden", DESCENDING)], {"name": "idx_hinchada_orden"}),
    ],
}
# $rank admite un solo campo de orden: puntos y, a igualdad, cantidad de plenos.
ORDEN_TABLA = {"$add": [{"$multiply": ["$puntos", 1000]}, "$exactos"]}
PROYECCION_PREDICCION = {
    "_id": 0, "codigo_partido": 1, "usuario_id": 1, "fase": 1, "equipo_local": 1, "equipo_visitante": 1,
    "goles_local": 1, "goles_visitante": 1, "resultado": 1, "puntos": 1, "acierto": 1,
    "resultado_real": 1, "creada_en": 1, "actualizada_en": 1,
}


def resultado(goles_local: int, goles_visitante: int) -> str:
    """L = gana el local, E = empate, V = gana el visitante."""
    return "L" if goles_local > goles_visitante else "V" if goles_local < goles_visitante else "E"


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
            tz_aware=True,  # las fechas del prode vuelven con zona UTC
        )
        self._db = self._cliente[settings.mongo_database]
        self._contexto_verificado = False
        self._prode_preparado = False

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

    # ----------------------------------------------------------------- portal
    def listar_equipos(self) -> list[dict[str, Any]]:
        with operacion(DEPENDENCIA, "equipos.find", _traducir):
            self._verificar_contexto()
            cursor = self._db.equipos.find({}, PROYECCION_EQUIPO_DETALLE).sort(
                [("grupo", 1), ("ranking_fifa", 1)]
            ).limit(100)
            return list(cursor)

    def jugadores_equipo(self, codigo_iso: str) -> list[dict[str, Any]]:
        proyeccion = {"_id": 1, "nombre": 1, "dorsal": 1, "posicion": 1, "edad": 1, "club_actual": 1}
        with operacion(DEPENDENCIA, "jugadores.find", _traducir):
            self._verificar_contexto()
            filas = list(self._db.jugadores.find({"codigo_equipo": codigo_iso}, proyeccion).sort("dorsal", 1).limit(60))
        return [{"id_jugador": f.pop("_id"), **f} for f in filas]

    # ------------------------------------------------------------------ prode
    def _preparar_prode(self) -> None:
        """Crea una sola vez las colecciones del prode con su validación e índices.
        create_index es idempotente; una colección ya existente no se modifica."""
        if self._prode_preparado:
            return
        self._verificar_contexto()
        existentes = set(self._db.list_collection_names(filter={"name": {"$in": list(ESQUEMAS_PRODE)}}))
        for nombre, esquema in ESQUEMAS_PRODE.items():
            if nombre not in existentes:
                try:
                    self._db.create_collection(nombre, validator={"$jsonSchema": esquema},
                                               validationLevel="strict", validationAction="error")
                except mongo_errors.CollectionInvalid:
                    pass  # la creó otra instancia de la API al mismo tiempo
        for nombre, indices in INDICES_PRODE.items():
            for claves, opciones in indices:
                self._db[nombre].create_index(claves, **opciones)
        self._prode_preparado = True

    def registrar_usuario_portal(self, alias: str, usuario_id: str, equipo_favorito: str | None) -> str:
        """Upsert por alias. Devuelve el usuario_id guardado: el de la primera vez si el alias
        ya existía, o el candidato recibido si es nuevo."""
        ahora = datetime.now(UTC)
        with operacion(DEPENDENCIA, "usuarios_portal.upsert", _traducir):
            self._preparar_prode()
            doc = self._db.usuarios_portal.find_one_and_update(
                {"_id": alias.lower()},
                {"$set": {"alias": alias, "equipo_favorito": equipo_favorito, "ultimo_ingreso": ahora},
                 "$setOnInsert": {"usuario_id": usuario_id, "creado_en": ahora}},
                upsert=True, return_document=ReturnDocument.AFTER, projection={"usuario_id": 1},
            )
            # Si ya figura en la tabla, refleja el alias y la hinchada con que ingresó ahora.
            self._db.tabla_posiciones.update_one(
                {"_id": doc["usuario_id"]}, {"$set": {"alias": alias, "equipo_favorito": equipo_favorito}})
        return doc["usuario_id"]

    def guardar_prediccion(self, p: dict[str, Any]) -> dict[str, Any] | None:
        """Crea o reemplaza el marcador pronosticado. None si esa predicción ya fue puntuada:
        el filtro puntos=null hace que el upsert choque con el _id existente."""
        ahora = datetime.now(UTC)
        with operacion(DEPENDENCIA, "predicciones.upsert", _traducir):
            self._preparar_prode()
            try:
                doc = self._db.predicciones.find_one_and_update(
                    {"_id": f"{p['codigo_partido']}:{p['usuario_id']}", "puntos": None},
                    {"$set": {**p, "resultado": resultado(p["goles_local"], p["goles_visitante"]),
                              "actualizada_en": ahora},
                     "$setOnInsert": {"creada_en": ahora, "acierto": None, "resultado_real": None,
                                      "liquidada_en": None}},
                    upsert=True, return_document=ReturnDocument.AFTER, projection=PROYECCION_PREDICCION,
                )
            except mongo_errors.DuplicateKeyError:
                return None
            # La fila del usuario aparece en la tabla desde su primer pronóstico.
            self._reconstruir_tabla(p["usuario_id"])
        return doc

    def predicciones_usuario(self, usuario_id: str) -> list[dict[str, Any]]:
        with operacion(DEPENDENCIA, "predicciones.find_usuario", _traducir):
            self._preparar_prode()
            return list(self._db.predicciones.find({"usuario_id": usuario_id}, PROYECCION_PREDICCION)
                        .sort("codigo_partido", 1).limit(200))

    def resumen_predicciones(self, codigo: str, usuario_id: str | None) -> dict[str, Any]:
        """Un solo $facet: reparto local/empate/visitante, marcadores más elegidos y promedios."""
        pipeline = [
            {"$match": {"codigo_partido": codigo}},
            {"$facet": {
                "por_resultado": [{"$group": {"_id": "$resultado", "n": {"$sum": 1}}}],
                "marcadores": [
                    {"$group": {"_id": {"l": "$goles_local", "v": "$goles_visitante"}, "n": {"$sum": 1}}},
                    {"$sort": {"n": -1, "_id.l": 1, "_id.v": 1}},
                    {"$limit": 5},
                ],
                "promedios": [{"$group": {"_id": None, "local": {"$avg": "$goles_local"},
                                          "visitante": {"$avg": "$goles_visitante"}}}],
            }},
        ]
        with operacion(DEPENDENCIA, "predicciones.resumen", _traducir):
            self._preparar_prode()
            f = next(self._db.predicciones.aggregate(pipeline))
            mia = (self._db.predicciones.find_one({"_id": f"{codigo}:{usuario_id}"}, PROYECCION_PREDICCION)
                   if usuario_id else None)
            liquidacion = self._db.liquidaciones.find_one({"_id": codigo}, {"_id": 0, "goles_local": 1,
                                                                             "goles_visitante": 1})
        conteo = {d["_id"]: d["n"] for d in f["por_resultado"]}
        prom = f["promedios"][0] if f["promedios"] else {}
        return {
            "total": sum(conteo.values()),
            "local": conteo.get("L", 0), "empate": conteo.get("E", 0), "visitante": conteo.get("V", 0),
            "promedio_goles_local": prom.get("local"), "promedio_goles_visitante": prom.get("visitante"),
            "marcadores": [{"goles_local": m["_id"]["l"], "goles_visitante": m["_id"]["v"], "cantidad": m["n"]}
                           for m in f["marcadores"]],
            "mi_prediccion": mia,
            "resultado_real": liquidacion,
        }

    def partidos_pendientes(self) -> list[str]:
        """Partidos con predicciones todavía sin puntuar (usa idx_partido_puntos)."""
        with operacion(DEPENDENCIA, "predicciones.distinct_pendientes", _traducir):
            self._preparar_prode()
            return sorted(self._db.predicciones.distinct("codigo_partido", {"puntos": None}))

    def liquidar_partido(self, codigo: str, goles_local: int, goles_visitante: int,
                         puntos_exacto: int, puntos_resultado: int) -> int:
        """Puntúa en el motor, con un update por pipeline, las predicciones pendientes del
        partido; registra la liquidación y rehace la tabla. Idempotente: una segunda llamada
        no encuentra pendientes y no cambia nada. Devuelve cuántas puntuó."""
        exacto = {"$and": [{"$eq": ["$goles_local", goles_local]}, {"$eq": ["$goles_visitante", goles_visitante]}]}
        acierta = {"$eq": ["$resultado", resultado(goles_local, goles_visitante)]}
        with operacion(DEPENDENCIA, "predicciones.liquidar", _traducir):
            self._preparar_prode()
            r = self._db.predicciones.update_many({"codigo_partido": codigo, "puntos": None}, [{"$set": {
                "acierto": {"$switch": {"branches": [{"case": exacto, "then": "exacto"},
                                                     {"case": acierta, "then": "resultado"}], "default": "ninguno"}},
                "puntos": {"$switch": {"branches": [{"case": exacto, "then": puntos_exacto},
                                                    {"case": acierta, "then": puntos_resultado}], "default": 0}},
                "resultado_real": {"goles_local": goles_local, "goles_visitante": goles_visitante},
                "liquidada_en": "$$NOW",
            }}])
            if r.modified_count:
                self._db.liquidaciones.update_one(
                    {"_id": codigo},
                    {"$set": {"goles_local": goles_local, "goles_visitante": goles_visitante,
                              "liquidado_en": datetime.now(UTC)},
                     "$inc": {"predicciones_puntuadas": r.modified_count}},
                    upsert=True,
                )
                self._reconstruir_tabla()
        return r.modified_count

    def reabrir_prode(self, codigos: list[str] | None = None) -> int:
        """scripts/reiniciar_demo.py: las predicciones de esos partidos (todos si es None)
        vuelven a pendientes, se borra su liquidación y se rehace la tabla."""
        por_partido = {"codigo_partido": {"$in": codigos}} if codigos is not None else {}
        with operacion(DEPENDENCIA, "predicciones.reabrir", _traducir):
            self._preparar_prode()
            r = self._db.predicciones.update_many(
                {**por_partido, "puntos": {"$ne": None}},
                {"$set": {"puntos": None, "acierto": None, "resultado_real": None, "liquidada_en": None}},
            )
            self._db.liquidaciones.delete_many({"_id": {"$in": codigos}} if codigos is not None else {})
            self._reconstruir_tabla()
        return r.modified_count

    def _reconstruir_tabla(self, usuario_id: str | None = None) -> None:
        """Vista materializada: agrupa predicciones por usuario, trae alias y selección
        favorita con $lookup y la escribe con $merge en tabla_posiciones."""
        pipeline: list[dict[str, Any]] = [{"$match": {"usuario_id": usuario_id}}] if usuario_id else []
        pipeline += [
            {"$group": {
                "_id": "$usuario_id",
                "puntos": {"$sum": {"$ifNull": ["$puntos", 0]}},
                "exactos": {"$sum": {"$cond": [{"$eq": ["$acierto", "exacto"]}, 1, 0]}},
                "aciertos": {"$sum": {"$cond": [{"$in": ["$acierto", ["exacto", "resultado"]]}, 1, 0]}},
                "pronosticos": {"$sum": 1},
                "puntuados": {"$sum": {"$cond": [{"$isNumber": "$puntos"}, 1, 0]}},
            }},
            {"$lookup": {"from": "usuarios_portal", "localField": "_id", "foreignField": "usuario_id", "as": "u"}},
            {"$set": {
                "alias": {"$ifNull": [{"$first": "$u.alias"}, "$_id"]},
                "equipo_favorito": {"$ifNull": [{"$first": "$u.equipo_favorito"}, None]},
                "orden": ORDEN_TABLA,
                "actualizada_en": "$$NOW",
            }},
            {"$unset": "u"},
            {"$merge": {"into": "tabla_posiciones", "on": "_id", "whenMatched": "replace", "whenNotMatched": "insert"}},
        ]
        self._db.predicciones.aggregate(pipeline)

    def tabla_posiciones(self, equipo: str | None, limit: int, usuario_id: str | None) -> dict[str, Any]:
        """Posición con $rank (empates comparten puesto), filtrable por hinchada; en el mismo
        $facet trae el top, la fila del usuario y el total de participantes."""
        pipeline = [
            {"$match": {"equipo_favorito": equipo} if equipo else {}},
            {"$setWindowFields": {"sortBy": {"orden": -1}, "output": {"posicion": {"$rank": {}}}}},
            {"$sort": {"posicion": 1, "alias": 1}},
            {"$project": {"_id": 0, "usuario_id": "$_id", "posicion": 1, "alias": 1, "equipo_favorito": 1,
                          "puntos": 1, "exactos": 1, "aciertos": 1, "pronosticos": 1, "puntuados": 1}},
            {"$facet": {
                "filas": [{"$limit": limit}],
                "mia": [{"$match": {"usuario_id": usuario_id or ""}}],
                "total": [{"$count": "n"}],
            }},
        ]
        with operacion(DEPENDENCIA, "tabla_posiciones.aggregate", _traducir):
            self._preparar_prode()
            f = next(self._db.tabla_posiciones.aggregate(pipeline))
        return {"filas": f["filas"], "mi_fila": f["mia"][0] if f["mia"] else None,
                "total_participantes": f["total"][0]["n"] if f["total"] else 0}

    # ------------------------------------------------------------------ salud
    def ping(self) -> None:
        """Conexión, autenticación, permiso de listado y contexto en una sola llamada liviana."""
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._contexto_verificado = False  # el chequeo de salud siempre vuelve a verificar
            self._verificar_contexto()

    def cerrar(self) -> None:
        self._cliente.close()

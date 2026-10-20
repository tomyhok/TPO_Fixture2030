"""MongoDB (Hito 4): equipos y jugadores. Cliente: pymongo, el mismo driver de la API (RF9).

| Capa          | Prueba                                   | Qué responde / qué NO permite concluir                 |
|---------------|------------------------------------------|--------------------------------------------------------|
| protocolo     | `hello` + `buildInfo` sin credenciales   | Habla el protocolo MongoDB / no dice si hay permisos   |
| autenticacion | `connectionStatus` con usuario           | La credencial es válida / no dice si puede leer la db   |
| autorizacion  | `listCollections` en MONGO_DATABASE      | Puede listar esa db / no dice si es la db correcta     |
| contexto      | colecciones esperadas presentes          | Es la db del Hito 4 / no dice si hay datos de prueba   |
| lectura       | `find_one` equipo + conteo jugadores     | La API podría leer / no mide rendimiento masivo        |
"""

from typing import Any

from conectividad.config import Config
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, warn

NOMBRE = "mongodb"


def _clasificar(exc: BaseException, capa: str) -> Paso:
    from pymongo import errors

    if isinstance(exc, errors.OperationFailure):
        if exc.code == 18:
            return fail(
                "credencial rechazada (AuthenticationFailed, código 18)",
                "MONGO_USER/MONGO_PASSWORD no coinciden con el usuario del servidor o MONGO_AUTH_DB es otra.",
                "Comparar el .env con MONGO_INITDB_ROOT_* del docker-compose.yml (sin publicar el valor).",
            )
        if exc.code == 13:
            return fail(
                f"identidad sin permiso para la operación (Unauthorized, código 13) en capa {capa}",
                "La conexión no está autenticada o el usuario no tiene un rol sobre esta database.",
                "Verificar que se envíen credenciales y el rol del usuario (db.getUser en admin).",
            )
        return fail(
            f"el servidor rechazó la operación: código {exc.code}",
            "Error de servidor ajeno a la red.",
            "Revisar el código de error en la documentación de MongoDB.",
        )
    if isinstance(exc, errors.ServerSelectionTimeoutError):
        return fail(
            f"no se completó el handshake MongoDB dentro del timeout ({resumen_excepcion(exc, 90)})",
            "El puerto aceptó TCP pero no respondió como MongoDB (puerto de otro producto) o el servidor "
            "no terminó de iniciar.",
            "Verificar MONGO_PORT y docker logs fixture2030-mongodb.",
        )
    if isinstance(exc, (errors.NetworkTimeout, errors.ExecutionTimeout)):
        return fail(
            "timeout de operación",
            "El servidor respondió al handshake pero la operación excedió TIMEOUT_OPERACION_S.",
            "Repetir con un timeout mayor y revisar carga del servidor.",
        )
    if isinstance(exc, errors.ConnectionFailure):
        return fail(
            f"conexión fallida ({resumen_excepcion(exc, 90)})",
            "El servidor cerró o rechazó la conexión.",
            "Revisar el estado del contenedor y la capa TCP.",
        )
    return clasificar_generico(exc, capa)


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    host, puerto = cfg.get("MONGO_HOST"), cfg.entero("MONGO_PORT")
    database = cfg.get("MONGO_DATABASE")
    colecciones = cfg.lista("MONGO_COLECCIONES")
    equipo = cfg.get("MONGO_EQUIPO_PRUEBA")
    conexion_s, operacion_s = cfg.decimal("TIMEOUT_CONEXION_S"), cfg.decimal("TIMEOUT_OPERACION_S")
    c = Cadena(registro, NOMBRE, capas, f"{host}:{puerto} database={database}", _clasificar)

    capa_configuracion(
        c, cfg,
        ["MONGO_HOST", "MONGO_PORT", "MONGO_USER", "MONGO_PASSWORD", "MONGO_AUTH_DB", "MONGO_DATABASE"],
        ["MONGO_HOST", "MONGO_PORT", "MONGO_DATABASE"] + (["MONGO_PASSWORD"] if cfg.get("MONGO_USER") else []),
    )
    capa_contenedor(c, cfg, "mongodb")
    capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "MONGO_PORT")
    if not (capas & (NATIVAS | {"sonda"})):
        return
    try:
        from pymongo import MongoClient
    except ImportError:
        c.sin_herramienta("pymongo (driver de MongoDB)")
        return

    comunes: dict[str, Any] = {
        "host": host,
        "port": puerto,
        "directConnection": True,
        "serverSelectionTimeoutMS": int(conexion_s * 1000),
        "connectTimeoutMS": int(conexion_s * 1000),
        "socketTimeoutMS": int(operacion_s * 1000),
        "appname": "fixture2030-diagnostico-h11",
    }
    anonimo = MongoClient(**comunes)
    usuario = cfg.get("MONGO_USER")
    cliente = (
        MongoClient(**comunes, username=usuario, password=cfg.get("MONGO_PASSWORD"), authSource=cfg.get("MONGO_AUTH_DB"))
        if usuario else anonimo
    )
    try:
        def protocolo() -> Paso:
            hola = anonimo.admin.command("hello")
            try:
                version = anonimo.admin.command("buildInfo")["version"]
            except Exception:  # noqa: BLE001 - algunas versiones lo restringen; no es una falla
                version = "no informada sin autenticación"
            return ok(
                f"primario={hola.get('isWritablePrimary')}, wire={hola.get('maxWireVersion')}, "
                f"MongoDB {version}"
            )

        def autenticacion() -> Paso:
            if not usuario:
                return warn(
                    "MONGO_USER vacío: conexión anónima",
                    "Si el servidor exige autenticación, las capas siguientes fallarán con código 13.",
                    "Configurar MONGO_USER/MONGO_PASSWORD.",
                )
            info = cliente.admin.command("connectionStatus")["authInfo"]
            usuarios = [f"{u['user']}@{u['db']}" for u in info.get("authenticatedUsers", [])]
            roles = sorted({r["role"] for r in info.get("authenticatedUserRoles", [])})
            if not usuarios:
                return fail("el servidor no informa usuario autenticado", "Credenciales no aplicadas.",
                            "Revisar MONGO_AUTH_DB.")
            return ok(f"autenticado como {', '.join(usuarios)} (roles: {', '.join(roles) or '-'})")

        def autorizacion() -> Paso:
            nombres = cliente[database].list_collection_names()
            return ok(f"permitido en '{database}' ({len(nombres)} colecciones)", valor=nombres)

        c.ejecutar("protocolo", "hello (sin credenciales)", protocolo)
        c.ejecutar("autenticacion", "connectionStatus", autenticacion)
        nombres = c.ejecutar("autorizacion", f"listCollections {database}", autorizacion)

        def contexto() -> Paso:
            presentes = set(nombres if nombres is not None else cliente[database].list_collection_names())
            faltan = [col for col in colecciones if col not in presentes]
            if not faltan:
                return ok(f"database '{database}' con las colecciones del módulo: {', '.join(colecciones)}")
            return fail(
                f"database '{database}' sin las colecciones {', '.join(faltan)}",
                "MongoDB no informa error por una database inexistente: devuelve listas vacías. "
                "MONGO_DATABASE apunta a otra base o no se ejecutó la carga del Hito 4.",
                "Verificar MONGO_DATABASE (show dbs) y ejecutar la carga del Hito 4.",
            )

        def lectura() -> Paso:
            col = cliente[database]
            doc = col.equipos.find_one({"_id": equipo}, {"_id": 1, "nombre": 1, "grupo": 1}, max_time_ms=int(operacion_s * 1000))
            jugadores = col.jugadores.count_documents({"codigo_equipo": equipo}, limit=100, maxTimeMS=int(operacion_s * 1000))
            if doc is None:
                return warn(
                    f"equipos.find_one(_id='{equipo}') -> null; jugadores: {jugadores}",
                    "La lectura funcionó pero el documento de prueba no existe (ausencia válida, no falla de conexión).",
                    "Revisar MONGO_EQUIPO_PRUEBA o la carga del Hito 4.",
                )
            return ok(
                f"equipos.find_one(_id='{equipo}') -> {doc.get('nombre')} (grupo {doc.get('grupo')}); "
                f"jugadores.count_documents(codigo_equipo='{equipo}', limit=100) = {jugadores}"
            )

        c.ejecutar("contexto", "colecciones esperadas", contexto)
        c.ejecutar("lectura", "find_one + count_documents", lectura)

        if sondas and c.activa("sonda") and c.bloqueada_por is None:
            col = cliente[database]
            def documento_inexistente() -> Paso:
                doc = col.equipos.find_one({"_id": "ZZZ"}, {"_id": 1})
                if doc is not None:
                    return fail("ZZZ existe", "No sirve como sonda de documento inexistente.",
                                "Elegir un identificador inexistente.")
                return ok("equipos.find_one(_id='ZZZ') -> None: ausencia válida")

            def coleccion_inexistente() -> Paso:
                nombre = "coleccion_inexistente_h11"
                if nombre in col.list_collection_names():
                    return fail(f"{nombre} existe", "No sirve como sonda de colección inexistente.",
                                "Elegir otra colección de prueba.")
                if col[nombre].find_one() is not None:
                    return fail("la colección devolvió un documento", "El estado cambió durante la prueba.", "Repetir.")
                return ok(f"{database}.{nombre}.find_one() -> None: colección inexistente, sin error del servidor")

            otra = f"{database}_inexistente_h11"
            def database_inexistente() -> Paso:
                if otra in cliente.list_database_names():
                    return fail(f"{otra} existe", "No sirve como sonda de database inexistente.",
                                "Elegir una database inexistente.")
                if cliente[otra].list_collection_names():
                    return fail("la database devolvió colecciones", "El estado cambió durante la prueba.", "Repetir.")
                return ok(f"{otra}.listCollections -> [] sin error: por eso el contexto verifica colecciones")

            c.ejecutar("sonda", "documento inexistente", documento_inexistente)
            c.ejecutar("sonda", "colección inexistente", coleccion_inexistente)
            c.ejecutar("sonda", "database inexistente", database_inexistente)
    finally:
        anonimo.close()
        if cliente is not anonimo:
            cliente.close()


"""Neo4j (Hito 5): partidos, eventos y relaciones. Cliente: driver oficial de Python (RF10).

Distingue el portal HTTP (Browser, puerto 7474), que la API NO usa, del acceso
Bolt (7687), que es el que usa el adaptador.

| Capa          | Prueba                                     | Qué NO permite concluir                         |
|---------------|--------------------------------------------|-------------------------------------------------|
| portal_http   | GET NEO4J_HTTP_URL (discovery JSON)        | Nada sobre Bolt ni credenciales                 |
| protocolo     | handshake Bolt crudo (magic 0x6060B017)    | Si la credencial sirve                          |
| autenticacion | driver.verify_authentication()             | Si la database configurada existe               |
| autorizacion  | SHOW CURRENT USER (database system)        | Permisos finos: Community no tiene RBAC         |
| contexto      | db.info() + db.labels() en NEO4J_DATABASE  | Si hay datos del partido de prueba              |
| lectura       | MATCH parametrizado y acotado de un partido | Rendimiento de recorridos profundos             |
"""

import socket

from conectividad.config import Config, host_puerto
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red, clasificar_error_http, http, puerto_cerrado
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, warn

NOMBRE = "neo4j"
MAGIC_BOLT = b"\x60\x60\xb0\x17"
# Propuestas [0, rango, menor, mayor]: 5.8 hasta 5.0, 4.4, y dos vacías.
PROPUESTAS_BOLT = bytes([0, 8, 8, 5, 0, 0, 4, 4]) + b"\x00" * 8

CYPHER_PARTIDO = """
MATCH (p:Partido {codigo_partido: $codigo})
OPTIONAL MATCH (e:Equipo)-[d:DISPUTA]->(p)
RETURN p.codigo_partido AS codigo, toString(p.fecha) AS fecha, collect(e.codigo_iso) AS equipos
LIMIT 1
"""
CYPHER_EVENTOS = """
MATCH (p:Partido {codigo_partido: $codigo})
OPTIONAL MATCH (ev:Evento)-[:CORRESPONDE_A]->(p)
RETURN p.codigo_partido AS codigo, count(ev) AS eventos
"""


def _clasificar(exc: BaseException, capa: str) -> Paso:
    from neo4j import exceptions as e

    codigo = getattr(exc, "code", "") or ""
    if isinstance(exc, e.AuthError) or "Unauthorized" in codigo:
        return fail(
            "credencial rechazada (Neo.ClientError.Security.Unauthorized)",
            "NEO4J_USER/NEO4J_PASSWORD no coinciden con NEO4J_AUTH del contenedor.",
            "Verificar el .env contra el compose; varios intentos fallidos bloquean la cuenta unos segundos.",
        )
    if codigo == "Neo.ClientError.Database.DatabaseNotFound":
        return fail(
            "database inexistente (Neo.ClientError.Database.DatabaseNotFound)",
            "NEO4J_DATABASE apunta a una base que no existe. Community solo tiene 'neo4j' y 'system'.",
            "Corregir NEO4J_DATABASE (SHOW DATABASES desde el Browser).",
        )
    if "Forbidden" in codigo:
        return fail(
            f"identidad sin permiso ({codigo})",
            "El usuario se autenticó pero no puede ejecutar la operación.",
            "Revisar roles del usuario (Enterprise) o usar el usuario de la API.",
        )
    if "TransactionTimedOut" in codigo:
        return fail("timeout de la transacción", "La consulta superó TIMEOUT_OPERACION_S.",
                    "Revisar la consulta y la carga del servidor.")
    if isinstance(exc, (e.ServiceUnavailable, e.SessionExpired)):
        return fail(
            f"servicio Bolt no disponible ({resumen_excepcion(exc, 90)})",
            "No se pudo abrir o mantener la conexión Bolt.",
            "Revisar la capa TCP y el estado del contenedor.",
        )
    return clasificar_generico(exc, capa)


def _handshake_bolt(direccion: str, puerto: int, timeout_s: float) -> Paso:
    with socket.create_connection((direccion, puerto), timeout=timeout_s) as s:
        s.settimeout(timeout_s)
        s.sendall(MAGIC_BOLT + PROPUESTAS_BOLT)
        respuesta = s.recv(64)
    if respuesta.startswith(b"HTTP"):
        return fail(
            f"el puerto respondió HTTP ({respuesta.split(b'\r\n')[0].decode(errors='replace')}), no Bolt",
            "Puerto incorrecto: se apunta al puerto HTTP del Browser (7474) en lugar de Bolt (7687).",
            "Corregir el puerto de NEO4J_URI.",
        )
    if len(respuesta) < 4:
        return fail(
            "el listener cerró la conexión sin responder el handshake Bolt",
            "El puerto pertenece a otro protocolo o el servidor no terminó de iniciar.",
            "Verificar el puerto y docker logs fixture2030-neo4j.",
        )
    _, _, menor, mayor = respuesta[:4]
    if mayor == 0:
        return fail("sin versión Bolt en común con el cliente", "Servidor o driver demasiado viejos/nuevos.",
                    "Actualizar el driver de Neo4j.")
    return ok(f"versión Bolt {mayor}.{menor} negociada (magic 0x6060B017)")


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    uri = cfg.get("NEO4J_URI")
    host, puerto = host_puerto(uri, 7687)
    database = cfg.get("NEO4J_DATABASE")
    partido = cfg.get("NEO4J_PARTIDO_PRUEBA")
    conexion_s, operacion_s = cfg.decimal("TIMEOUT_CONEXION_S"), cfg.decimal("TIMEOUT_OPERACION_S")
    c = Cadena(registro, NOMBRE, capas, f"{uri} database={database}", _clasificar)

    capa_configuracion(
        c, cfg,
        ["NEO4J_URI", "NEO4J_HTTP_URL", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"],
        ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"],
    )
    capa_contenedor(c, cfg, "neo4j")

    url_http = cfg.get("NEO4J_HTTP_URL")

    def portal() -> Paso:
        try:
            r = http("GET", url_http, operacion_s, headers={"Accept": "application/json"})
        except OSError as exc:
            return clasificar_error_http(exc, "portal_http")
        if r.status != 200:
            return fail(f"HTTP {r.status}", "El servidor HTTP de Neo4j no respondió como se esperaba.",
                        "Revisar NEO4J_HTTP_URL y los logs.")
        info = r.json() or {}
        return ok(
            f"HTTP 200: Neo4j {info.get('neo4j_version')} {info.get('neo4j_edition')}; anuncia bolt_direct="
            f"{info.get('bolt_direct')}. La API no usa este puerto: no prueba Bolt"
        )

    if not c.bloqueada_por:
        c.ejecutar("portal_http", "GET Browser/discovery", portal, destino=url_http)
    direccion = capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "NEO4J_URI")
    if not (capas & (NATIVAS | {"sonda"})):
        return
    c.ejecutar("protocolo", "handshake Bolt", lambda: _handshake_bolt(direccion or host, puerto, operacion_s))
    try:
        from neo4j import READ_ACCESS, GraphDatabase, Query
    except ImportError:
        c.sin_herramienta("neo4j (driver de Python)", tuple(NATIVAS - {"protocolo"}) + ("sonda",))
        return

    driver = GraphDatabase.driver(
        uri,
        auth=(cfg.get("NEO4J_USER"), cfg.get("NEO4J_PASSWORD")),
        connection_timeout=conexion_s,
        connection_acquisition_timeout=conexion_s + operacion_s,
        user_agent="fixture2030-diagnostico-h11",
    )
    try:
        def autenticacion() -> Paso:
            if driver.verify_authentication():
                return ok(f"usuario '{cfg.get('NEO4J_USER')}' autenticado por Bolt")
            return fail(
                "credencial rechazada (verify_authentication = False)",
                "NEO4J_USER/NEO4J_PASSWORD no coinciden con NEO4J_AUTH del contenedor.",
                "Verificar el .env contra el compose.",
            )

        def autorizacion() -> Paso:
            with driver.session(database="system", default_access_mode=READ_ACCESS) as s:
                fila = s.run(Query("SHOW CURRENT USER YIELD user, roles", timeout=operacion_s)).single()
            roles = fila["roles"]
            return ok(
                f"identidad '{fila['user']}' reconocida; roles={roles if roles is not None else 'null'}"
                + (" (Community: sin RBAC, toda identidad autenticada puede leer)" if roles is None else "")
            )

        def contexto() -> Paso:
            with driver.session(database=database, default_access_mode=READ_ACCESS) as s:
                nombre = s.run(Query("CALL db.info() YIELD name RETURN name", timeout=operacion_s)).single()["name"]
                etiquetas = s.run(Query("CALL db.labels() YIELD label RETURN collect(label) AS l",
                                        timeout=operacion_s)).single()["l"]
            if "Partido" not in etiquetas:
                return fail(
                    f"database '{nombre}' sin la etiqueta Partido (etiquetas: {etiquetas})",
                    "Es otra base o no se ejecutó la carga del Hito 5.",
                    "Ejecutar estructura.cypher y carga.cypher (scripts/preparar_datos.sh del Hito 10).",
                )
            return ok(f"database '{nombre}' seleccionada; etiquetas: {', '.join(etiquetas)}")

        def lectura() -> Paso:
            with driver.session(database=database, default_access_mode=READ_ACCESS) as s:
                fila = s.run(Query(CYPHER_PARTIDO, timeout=operacion_s), codigo=partido).single()
            if fila is None:
                return warn(
                    f"MATCH (p:Partido {{codigo_partido:'{partido}'}}) -> sin filas",
                    "La consulta funcionó pero el partido de prueba no existe (ausencia válida).",
                    "Revisar NEO4J_PARTIDO_PRUEBA o la carga del Hito 5.",
                )
            return ok(f"Partido {fila['codigo']} ({fila['fecha']}): equipos {', '.join(sorted(fila['equipos']))} "
                      "[Cypher parametrizado, LIMIT 1, timeout de operación]")

        c.ejecutar("autenticacion", "verify_authentication", autenticacion)
        c.ejecutar("autorizacion", "SHOW CURRENT USER", autorizacion)
        c.ejecutar("contexto", f"db.info() en '{database}'", contexto)
        c.ejecutar("lectura", "MATCH parametrizado", lectura)

        if sondas and c.activa("sonda") and c.bloqueada_por is None:
            def inexistente() -> Paso:
                with driver.session(database=database, default_access_mode=READ_ACCESS) as s:
                    fila = s.run(Query(CYPHER_EVENTOS, timeout=operacion_s), codigo="P-999").single()
                return ok(f"partido P-999 -> {'sin filas' if fila is None else fila.data()}: "
                          "partido inexistente (la API responde 404)")

            def vacio() -> Paso:
                codigo = cfg.get("NEO4J_PARTIDO_SIN_EVENTOS")
                with driver.session(database=database, default_access_mode=READ_ACCESS) as s:
                    fila = s.run(Query(CYPHER_EVENTOS, timeout=operacion_s), codigo=codigo).single()
                if fila is None:
                    return warn(f"partido {codigo} inexistente: no sirve como ejemplo de resultado vacío")
                return ok(f"partido {codigo} existe con {fila['eventos']} eventos: resultado vacío válido "
                          "(la API responde 200 con lista vacía)")

            def database_inexistente() -> Paso:
                try:
                    with driver.session(database="noexiste_h11") as s:
                        s.run(Query("RETURN 1", timeout=operacion_s)).consume()
                except Exception as exc:  # noqa: BLE001 - se espera un error de cliente
                    codigo = getattr(exc, "code", type(exc).__name__)
                    return ok(f"database 'noexiste_h11' -> {codigo}: error de contexto, no de conexión "
                              "(la API lo traduce a 503)")
                return fail("la database inexistente no produjo error", "Comportamiento inesperado.",
                            "Revisar la versión de Neo4j.")

            def conexion_fallida() -> Paso:
                libre = puerto_cerrado()
                otro = GraphDatabase.driver(f"bolt://127.0.0.1:{libre}", auth=("neo4j", "x"), connection_timeout=1)
                try:
                    otro.verify_connectivity()
                except Exception as exc:  # noqa: BLE001 - se espera ServiceUnavailable
                    return ok(f"bolt://127.0.0.1:{libre} sin listener -> {type(exc).__name__}: "
                              "error de conexión, distinto de 'sin filas'")
                finally:
                    otro.close()
                return fail("se esperaba un error de conexión", "Había un listener en el puerto.", "-")

            c.ejecutar("sonda", "partido inexistente", inexistente)
            c.ejecutar("sonda", "resultado vacío", vacio)
            c.ejecutar("sonda", "database inexistente", database_inexistente)
            c.ejecutar("sonda", "error de conexión", conexion_fallida)
    finally:
        driver.close()

"""Cassandra (Hito 6): comentarios. Cliente: cassandra-driver, el mismo de la API (RF11).

| Capa          | Prueba                                         | Qué NO permite concluir                      |
|---------------|------------------------------------------------|----------------------------------------------|
| protocolo     | frame CQL OPTIONS -> SUPPORTED (sin driver)    | Si el servidor exige credenciales            |
| autenticacion | frame CQL STARTUP -> READY / AUTHENTICATE      | Si el keyspace existe                        |
| autorizacion  | sesión del driver + SELECT system.local        | Permisos sobre el keyspace del módulo        |
| contexto      | metadata: keyspace, tabla, clave de partición, DC | Si hay datos en la partición de prueba    |
| lectura       | SELECT con clave de partición completa, LIMIT  | Rendimiento de escritura o de lecturas masivas |
"""

import logging
import socket
import struct
import time

from conectividad.config import Config
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, warn

NOMBRE = "cassandra"
SHARDS = 4  # mismo valor que el productor del Hito 6
OPCODES = {0x00: "ERROR", 0x02: "READY", 0x03: "AUTHENTICATE", 0x06: "SUPPORTED"}


# ------------------------------------------------- protocolo CQL sin driver
def _frame(opcode: int, cuerpo: bytes = b"", stream: int = 1) -> bytes:
    return struct.pack(">BBhBI", 0x04, 0, stream, opcode, len(cuerpo)) + cuerpo


def _leer_frame(s: socket.socket) -> tuple[int, int, bytes]:
    cabecera = b""
    while len(cabecera) < 9:
        parte = s.recv(9 - len(cabecera))
        if not parte:
            raise ConnectionError("el listener cerró la conexión sin enviar un frame CQL")
        cabecera += parte
    version, _, _, opcode, largo = struct.unpack(">BBhBI", cabecera)
    if version & 0x7F not in (3, 4, 5, 6) or not version & 0x80:
        raise ValueError(f"respuesta que no es CQL (primeros bytes {cabecera[:4]!r})")
    cuerpo = b""
    while len(cuerpo) < largo:
        cuerpo += s.recv(largo - len(cuerpo))
    return version, opcode, cuerpo


def _string_multimap(datos: bytes) -> dict[str, list[str]]:
    pos = 0

    def corto() -> int:
        nonlocal pos
        valor = struct.unpack(">H", datos[pos : pos + 2])[0]
        pos += 2
        return valor

    def cadena() -> str:
        nonlocal pos
        largo = corto()
        valor = datos[pos : pos + largo].decode("utf-8")
        pos += largo
        return valor

    resultado = {}
    for _ in range(corto()):
        clave = cadena()
        resultado[clave] = [cadena() for _ in range(corto())]
    return resultado


def _string_map(valores: dict[str, str]) -> bytes:
    salida = struct.pack(">H", len(valores))
    for clave, valor in valores.items():
        salida += struct.pack(">H", len(clave)) + clave.encode() + struct.pack(">H", len(valor)) + valor.encode()
    return salida


def _options(direccion: str, puerto: int, timeout_s: float) -> Paso:
    with socket.create_connection((direccion, puerto), timeout=timeout_s) as s:
        s.settimeout(timeout_s)
        s.sendall(_frame(0x05))
        version, opcode, cuerpo = _leer_frame(s)
    if opcode != 0x06:
        return fail(f"OPTIONS respondió {OPCODES.get(opcode, hex(opcode))}", "Respuesta CQL inesperada.",
                    "Revisar la versión de Cassandra.")
    soportado = _string_multimap(cuerpo)
    return ok(
        f"OPTIONS -> SUPPORTED: CQL {', '.join(soportado.get('CQL_VERSION', []))}; "
        f"protocolos {', '.join(soportado.get('PROTOCOL_VERSIONS', []))}"
    )


def _startup(direccion: str, puerto: int, timeout_s: float) -> Paso:
    with socket.create_connection((direccion, puerto), timeout=timeout_s) as s:
        s.settimeout(timeout_s)
        s.sendall(_frame(0x01, _string_map({"CQL_VERSION": "3.0.0"})))
        _, opcode, cuerpo = _leer_frame(s)
    if opcode == 0x02:
        return ok("STARTUP -> READY: el servidor no exige autenticación (AllowAllAuthenticator del "
                  "laboratorio; cualquier cliente que alcance el puerto puede operar)")
    if opcode == 0x03:
        autenticador = cuerpo[2:].decode(errors="replace")
        return fail(
            f"STARTUP -> AUTHENTICATE ({autenticador}): el servidor exige credenciales",
            "Cassandra tiene un autenticador activo y la API no envía usuario ni contraseña.",
            "Agregar credenciales al adaptador o volver a AllowAllAuthenticator en el laboratorio.",
        )
    return fail(f"STARTUP -> {OPCODES.get(opcode, hex(opcode))}", "Respuesta CQL inesperada.",
                "Revisar los logs de Cassandra.")


def _clasificar(exc: BaseException, capa: str) -> Paso:
    from cassandra import InvalidRequest, OperationTimedOut, ReadTimeout, Unauthorized
    from cassandra.auth import AuthenticationFailed
    from cassandra.cluster import NoHostAvailable

    if isinstance(exc, NoHostAvailable):
        texto = str(exc)
        if "keyspace" in texto.lower():
            return fail(
                "el driver no pudo usar el keyspace configurado (NoHostAvailable ... using keyspace)",
                "El keyspace no existe: el driver lo informa como NoHostAvailable aunque la red funcione.",
                "Verificar CASSANDRA_KEYSPACE (DESCRIBE KEYSPACES) y ejecutar 01-keyspace.cql.",
            )
        return fail(
            f"ningún nodo disponible ({resumen_excepcion(exc, 100)})",
            "El driver no logró sesión con ningún contact point (red, puerto o nodo iniciando).",
            "Revisar la capa TCP y docker logs fixture2030-cassandra.",
        )
    if isinstance(exc, (OperationTimedOut, ReadTimeout)):
        return fail(
            f"timeout ({type(exc).__name__})",
            "El nodo no respondió dentro del límite: timeout de conexión u operación, no consulta inválida.",
            "Repetir con TIMEOUT_OPERACION_S mayor y revisar la carga del nodo.",
        )
    if isinstance(exc, InvalidRequest):
        return fail(
            f"consulta inválida ({resumen_excepcion(exc, 120)})",
            "El servidor respondió: la red funciona, el problema es el contexto (keyspace/tabla) o la consulta.",
            "Verificar CASSANDRA_KEYSPACE, CASSANDRA_TABLA y el modelo del Hito 6.",
        )
    if isinstance(exc, AuthenticationFailed):
        return fail("credencial rechazada", "Usuario o contraseña de Cassandra inválidos.", "Revisar credenciales.")
    if isinstance(exc, Unauthorized):
        return fail("identidad sin permiso", "El rol no tiene SELECT sobre el recurso.", "Revisar GRANT del rol.")
    if isinstance(exc, (ConnectionError, ValueError, OSError)):
        return fail(
            f"el listener no respondió con el protocolo CQL ({exc})",
            "Puerto incorrecto (otro producto) o nodo que todavía no abrió el transporte nativo.",
            "Verificar CASSANDRA_PORT (9042) y esperar el healthcheck del contenedor.",
        )
    return clasificar_generico(exc, capa)


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    hosts = cfg.lista("CASSANDRA_HOSTS")
    host, puerto = (hosts[0] if hosts else ""), cfg.entero("CASSANDRA_PORT")
    keyspace, tabla, dc = cfg.get("CASSANDRA_KEYSPACE"), cfg.get("CASSANDRA_TABLA"), cfg.get("CASSANDRA_DC")
    partido, ventana = cfg.get("CASSANDRA_PARTIDO_PRUEBA"), cfg.get("CASSANDRA_VENTANA_PRUEBA")
    conexion_s, operacion_s = cfg.decimal("TIMEOUT_CONEXION_S"), cfg.decimal("TIMEOUT_OPERACION_S")
    c = Cadena(registro, NOMBRE, capas, f"{host}:{puerto} keyspace={keyspace}", _clasificar)

    capa_configuracion(
        c, cfg,
        ["CASSANDRA_HOSTS", "CASSANDRA_PORT", "CASSANDRA_KEYSPACE", "CASSANDRA_DC", "CASSANDRA_TABLA"],
        ["CASSANDRA_HOSTS", "CASSANDRA_PORT", "CASSANDRA_KEYSPACE", "CASSANDRA_DC"],
    )
    capa_contenedor(c, cfg, "cassandra")
    direccion = capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "CASSANDRA_PORT") or host
    if not (capas & (NATIVAS | {"sonda"})):
        return
    c.ejecutar("protocolo", "frame OPTIONS", lambda: _options(direccion, puerto, operacion_s))
    c.ejecutar("autenticacion", "frame STARTUP", lambda: _startup(direccion, puerto, operacion_s))
    try:
        from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
        from cassandra.policies import DCAwareRoundRobinPolicy
        from cassandra.query import dict_factory
    except ImportError:
        c.sin_herramienta("cassandra-driver", ("autorizacion", "contexto", "lectura", "sonda"))
        return

    logging.getLogger("cassandra").setLevel(logging.CRITICAL)  # el driver loguea hosts y reintentos
    perfil = ExecutionProfile(
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=dc),
        request_timeout=operacion_s,
        row_factory=dict_factory,
    )
    cluster = Cluster(
        contact_points=hosts,
        port=puerto,
        execution_profiles={EXEC_PROFILE_DEFAULT: perfil},
        protocol_version=5,
        connect_timeout=conexion_s,
        control_connection_timeout=conexion_s,
    )
    try:
        estado: dict = {}

        def autorizacion() -> Paso:
            estado["sesion"] = cluster.connect()
            fila = estado["sesion"].execute(
                "SELECT release_version, cluster_name, data_center FROM system.local"
            ).one()
            estado["local"] = fila
            return ok(f"sesión del driver abierta; SELECT system.local permitido: Cassandra "
                      f"{fila['release_version']}, cluster '{fila['cluster_name']}', DC '{fila['data_center']}'")

        def contexto() -> Paso:
            local = estado.get("local") or {}
            if local and local.get("data_center") != dc:
                return fail(
                    f"CASSANDRA_DC='{dc}' pero el nodo está en '{local.get('data_center')}'",
                    "Con DCAwareRoundRobinPolicy el driver no enviaría consultas a nodos de otro DC.",
                    "Corregir CASSANDRA_DC.",
                )
            ks = cluster.metadata.keyspaces.get(keyspace)
            if ks is None:
                return fail(
                    f"keyspace '{keyspace}' inexistente (keyspaces: {', '.join(sorted(cluster.metadata.keyspaces))})",
                    "La red y el protocolo funcionan: el contexto configurado no existe. La API lo vería "
                    "como NoHostAvailable al conectar con ese keyspace.",
                    "Corregir CASSANDRA_KEYSPACE o ejecutar 01-keyspace.cql y 02-tablas.cql.",
                )
            t = ks.tables.get(tabla)
            if t is None:
                return fail(f"tabla {keyspace}.{tabla} inexistente", "Falta el esquema del Hito 6.",
                            "Ejecutar 02-tablas.cql.")
            particion = ", ".join(col.name for col in t.partition_key)
            clustering = ", ".join(col.name for col in t.clustering_key)
            replicacion = ks.replication_strategy.export_for_schema()
            return ok(f"keyspace '{keyspace}' ({replicacion}); {tabla}: partición ({particion}), "
                      f"clustering ({clustering}); DC '{dc}' coincide")

        def lectura() -> Paso:
            sesion = estado["sesion"]
            sentencia = sesion.prepare(
                f"SELECT id_comentario FROM {keyspace}.{tabla} WHERE id_partido = ? AND ventana = ? AND shard = ? LIMIT 5"
            )
            filas = [len(list(sesion.execute(sentencia, (partido, ventana, shard), timeout=operacion_s)))
                     for shard in range(SHARDS)]
            detalle = (f"partición completa ({partido}, {ventana}, shard 0..{SHARDS - 1}), LIMIT 5 c/u: "
                       f"{sum(filas)} filas {filas}")
            if not sum(filas):
                return warn(detalle, "La consulta funcionó pero la ventana de prueba no tiene comentarios "
                            "(ausencia válida).", "Revisar CASSANDRA_VENTANA_PRUEBA o 03-carga-muestra.cql.")
            return ok(detalle)

        c.ejecutar("autorizacion", "sesión + system.local", autorizacion)
        c.ejecutar("contexto", "metadata keyspace/tabla", contexto)
        c.ejecutar("lectura", "SELECT por partición", lectura)

        if sondas and c.activa("sonda") and "sesion" in estado:
            from cassandra import InvalidRequest
            from cassandra.cluster import NoHostAvailable

            sesion = estado["sesion"]

            def esperar_error(cql: str, timeout: float, esperado: type, explicacion: str) -> Paso:
                try:
                    sesion.execute(cql, timeout=timeout)
                except esperado as exc:
                    mensaje = getattr(exc, "message", None) or str(exc) or type(exc).__name__
                    return ok(f"{type(exc).__name__}: {' '.join(mensaje.split())[:90]} -> {explicacion}")
                return fail("la consulta no produjo el error esperado", "Comportamiento inesperado.", "-")

            c.ejecutar("sonda", "tabla inexistente", lambda: esperar_error(
                f"SELECT * FROM {keyspace}.tabla_inexistente_h11 LIMIT 1", operacion_s, InvalidRequest,
                "consulta inválida (respuesta del servidor), no timeout"))
            c.ejecutar("sonda", "keyspace inexistente", lambda: esperar_error(
                "SELECT * FROM keyspace_inexistente_h11.t LIMIT 1", operacion_s, InvalidRequest,
                "contexto inexistente informado por el servidor"))
            c.ejecutar("sonda", "partición incompleta", lambda: esperar_error(
                f"SELECT * FROM {keyspace}.{tabla} WHERE id_partido = '{partido}' LIMIT 1", operacion_s,
                InvalidRequest, "el modelo exige la clave de partición completa (sin ALLOW FILTERING)"))
            def timeout_conexion() -> Paso:
                # 10.255.255.1: dirección privada sin host; el SYN no recibe respuesta.
                sin_ruta = Cluster(contact_points=["10.255.255.1"], port=puerto, protocol_version=5,
                                   connect_timeout=1, control_connection_timeout=1)
                inicio = time.perf_counter()
                try:
                    sin_ruta.connect()
                except NoHostAvailable as exc:
                    ms = (time.perf_counter() - inicio) * 1000
                    causa = "; ".join(type(e).__name__ for e in exc.errors.values()) or "sin detalle"
                    return ok(f"10.255.255.1:{puerto} -> NoHostAvailable({causa}) en {ms:.0f} ms: timeout de "
                              "conexión (sin respuesta del servidor), distinto de InvalidRequest (el servidor respondió)")
                finally:
                    sin_ruta.shutdown()
                return fail("se esperaba un timeout de conexión", "La dirección respondió.", "-")

            c.ejecutar("sonda", "timeout de conexión", timeout_conexion)
    finally:
        cluster.shutdown()

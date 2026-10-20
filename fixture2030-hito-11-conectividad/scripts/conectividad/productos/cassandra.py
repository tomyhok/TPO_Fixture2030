"""Cassandra (Hito 6): comentarios. Cliente: cassandra-driver, el mismo de la API (RF11).

| Capa          | Prueba                                         | Qué NO permite concluir                      |
|---------------|------------------------------------------------|----------------------------------------------|
| protocolo     | sesión CQL mediante el driver oficial         | Permisos sobre el contexto del módulo        |
| autenticacion | sesión aceptada sin credenciales (lab)          | Si el keyspace existe                        |
| autorizacion  | sesión del driver + SELECT system.local        | Permisos sobre el keyspace del módulo        |
| contexto      | metadata: keyspace, tabla, clave de partición, DC | Si hay datos en la partición de prueba    |
| lectura       | SELECT con clave de partición completa, LIMIT  | Rendimiento de escritura o de lecturas masivas |
"""

import logging

from conectividad.config import Config
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, warn

NOMBRE = "cassandra"
SHARDS = 4  # mismo valor que el productor del Hito 6


def _clasificar(exc: BaseException, capa: str) -> Paso:
    from cassandra import AuthenticationFailed, InvalidRequest, OperationTimedOut, ReadTimeout, Unauthorized
    from cassandra.cluster import NoHostAvailable

    if isinstance(exc, NoHostAvailable):
        if any(isinstance(causa, AuthenticationFailed) for causa in exc.errors.values()):
            return fail("credencial requerida o rechazada por CQL", "La API no configura autenticación de Cassandra en este laboratorio.",
                        "Revisar el autenticador del servidor y la identidad configurada.")
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
    capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "CASSANDRA_PORT")
    if not (capas & (NATIVAS | {"sonda"})):
        return
    try:
        from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
        from cassandra.policies import DCAwareRoundRobinPolicy
        from cassandra.query import dict_factory
    except ImportError:
        c.sin_herramienta("cassandra-driver")
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

        def obtener_sesion():
            # También inicializa la sesión si se pide únicamente contexto o lectura.
            if "sesion" not in estado:
                estado["sesion"] = cluster.connect()
            return estado["sesion"]

        def protocolo() -> Paso:
            from cassandra import AuthenticationFailed
            from cassandra.cluster import NoHostAvailable
            try:
                obtener_sesion()
            except NoHostAvailable as exc:
                if any(isinstance(causa, AuthenticationFailed) for causa in exc.errors.values()):
                    return ok("el servidor respondió CQL y rechazó la identidad; se informa en autenticación")
                raise
            return ok("sesión CQL negociada por cassandra-driver; incluye el intercambio de identidad")

        def autenticacion() -> Paso:
            obtener_sesion()
            return ok("sesión aceptada sin credenciales, igual que la API del laboratorio; no prueba permisos sobre las tablas")

        def autorizacion() -> Paso:
            fila = obtener_sesion().execute(
                "SELECT release_version, cluster_name, data_center FROM system.local", timeout=operacion_s
            ).one()
            estado["local"] = fila
            return ok(f"SELECT system.local permitido: Cassandra {fila['release_version']}, "
                      f"cluster '{fila['cluster_name']}', DC '{fila['data_center']}'")

        def contexto() -> Paso:
            obtener_sesion()
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
                      f"clustering ({clustering}); DC configurado '{dc}'")

        def lectura() -> Paso:
            verificacion = contexto()
            if verificacion.estado != "OK":
                return verificacion
            sesion = obtener_sesion()
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

        c.ejecutar("protocolo", "sesión CQL (driver)", protocolo)
        c.ejecutar("autenticacion", "identidad de la sesión", autenticacion)
        c.ejecutar("autorizacion", "SELECT system.local", autorizacion)
        c.ejecutar("contexto", "metadata keyspace/tabla", contexto)
        c.ejecutar("lectura", "SELECT por partición", lectura)

        if sondas and c.activa("sonda") and c.bloqueada_por is None:
            from cassandra import InvalidRequest
            sesion = obtener_sesion()
            contexto_sonda = contexto()
            if contexto_sonda.estado != "OK":
                from conectividad.registro import skip
                c.registrar("sonda", "prerrequisitos", skip(
                    "no se prueban tablas ni particiones: " + contexto_sonda.detalle), None)
                return

            def esperar_error(cql: str, terminos: tuple[str, ...], explicacion: str) -> Paso:
                try:
                    sesion.execute(cql, timeout=operacion_s)
                except InvalidRequest as exc:
                    mensaje = getattr(exc, "message", None) or str(exc)
                    if not all(t in mensaje.lower() for t in terminos):
                        return fail(f"InvalidRequest de otra causa: {mensaje[:160]}",
                                    "La consulta falló, pero no por la condición que esta sonda evalúa.",
                                    "Revisar el contexto y el mensaje antes de interpretar la prueba.")
                    return ok(f"InvalidRequest: {' '.join(mensaje.split())[:120]} -> {explicacion}")
                return fail("la consulta no produjo el error esperado", "La condición negativa no se verificó.",
                            "Revisar que el recurso de prueba sea inexistente.")

            c.ejecutar("sonda", "tabla inexistente", lambda: esperar_error(
                f"SELECT * FROM {keyspace}.tabla_inexistente_h11 LIMIT 1", ("tabla_inexistente_h11",),
                "tabla inexistente; el servidor respondió"))
            c.ejecutar("sonda", "keyspace inexistente", lambda: esperar_error(
                "SELECT * FROM keyspace_inexistente_h11.t LIMIT 1", ("keyspace_inexistente_h11",),
                "keyspace inexistente; el servidor respondió"))
            c.ejecutar("sonda", "partición incompleta", lambda: esperar_error(
                f"SELECT * FROM {keyspace}.{tabla} WHERE id_partido = '{partido}' LIMIT 1", ("filtering",),
                "la consulta no respeta el patrón de partición y exigiría ALLOW FILTERING"))
    finally:
        cluster.shutdown()

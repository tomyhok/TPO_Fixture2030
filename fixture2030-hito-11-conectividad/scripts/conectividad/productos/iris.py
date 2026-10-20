"""InterSystems IRIS (Hito 9): actas oficiales. Clientes: Native API para metadatos y DB-API/SQL para leer como la API (RF14).

Distingue el portal HTTP (52773), que la API NO usa, del Superserver (1972).

| Capa          | Prueba                                          | Qué NO permite concluir                    |
|---------------|-------------------------------------------------|--------------------------------------------|
| portal_http   | GET Management Portal                           | Nada sobre el Superserver                  |
| protocolo     | iris.connect: el Superserver responde           | Si la credencial sirve (ver abajo)         |
| autenticacion | iris.connect con usuario/namespace              | Permisos para ejecutar clases              |
| autorizacion  | %SYSTEM.Version.GetNumber (Native API)          | Si el namespace es el del módulo           |
| contexto      | %SYSTEM.SYS.NameSpace + clase compilada         | Si existe el acta de prueba                |
| lectura       | SELECT del acta por DB-API (Hito 9)    | Rendimiento de escrituras                  |

Particularidades medidas en el laboratorio:
  * IRIS responde "Access Denied" tanto a una credencial inválida como a un
    namespace inexistente. Para separarlos se reintenta con el namespace
    alternativo (USER) y se consulta %SYS.Namespace.Exists.
  * iris.connect() contra un puerto que no es el Superserver (p. ej. 52773)
    se queda esperando aunque se le pase timeout: cada llamada corre en un
    hilo con límite de espera.
  * Un login fallido cuenta para el bloqueo de la cuenta: el diagnóstico nunca
    prueba contraseñas incorrectas contra IRIS.
"""

import time

from conectividad.config import Config
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import LimiteExcedido, capa_red, clasificar_error_http, con_limite, http
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, warn

NOMBRE = "iris"


def _clasificar(exc: BaseException, capa: str) -> Paso:
    texto = str(exc)
    if "<PROTECT>" in texto or "%Native_ClassExecution" in texto:
        return fail(
            f"identidad sin permiso ({resumen_excepcion(exc, 80)})",
            "El usuario se autenticó pero su rol no permite ejecutar la operación (falta %Native_ClassExecution "
            "o el recurso de la base).",
            "Revisar el rol de lectura FixtureAPIRead (scripts/preparar_datos.sh del Hito 10).",
        )
    if "<CLASS DOES NOT EXIST>" in texto:
        return fail(
            f"clase inexistente en el namespace ({resumen_excepcion(exc, 80)})",
            "El namespace es otro o no se compilaron las clases del Hito 9.",
            "Ejecutar scripts/preparar_datos.sh del Hito 10.",
        )
    if isinstance(exc, LimiteExcedido):
        return fail(
            f"el Superserver no respondió: {exc}",
            "El listener aceptó TCP pero no habla el protocolo de IRIS (p. ej. puerto 52773 del portal) o "
            "IRIS está bloqueado. El cliente nativo no corta solo: el límite lo pone el diagnóstico.",
            "Verificar IRIS_PORT (1972).",
        )
    if "COMMUNICATION LINK ERROR" in texto:
        return fail(
            f"error de comunicación ({resumen_excepcion(exc, 100)})",
            "La conexión con el Superserver se cortó o fue rechazada.",
            "Revisar la capa TCP y el contenedor.",
        )
    return clasificar_generico(exc, capa)


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    host, puerto = cfg.get("IRIS_HOST"), cfg.entero("IRIS_PORT")
    namespace, alternativo = cfg.get("IRIS_NAMESPACE"), cfg.get("IRIS_NAMESPACE_ALTERNATIVO")
    usuario, clase, acta = cfg.get("IRIS_USER"), cfg.get("IRIS_CLASE"), cfg.get("IRIS_ACTA_PRUEBA")
    conexion_s, operacion_s = cfg.decimal("TIMEOUT_CONEXION_S"), cfg.decimal("TIMEOUT_OPERACION_S")
    limite = conexion_s + operacion_s
    c = Cadena(registro, NOMBRE, capas, f"{host}:{puerto} namespace={namespace}", _clasificar)

    capa_configuracion(
        c, cfg,
        ["IRIS_HOST", "IRIS_PORT", "IRIS_PORTAL_URL", "IRIS_NAMESPACE", "IRIS_USER", "IRIS_PASSWORD"],
        ["IRIS_HOST", "IRIS_PORT", "IRIS_NAMESPACE", "IRIS_USER", "IRIS_PASSWORD"],
    )
    capa_contenedor(c, cfg, "iris")

    portal = cfg.get("IRIS_PORTAL_URL")

    def probar_portal() -> Paso:
        try:
            r = http("GET", portal, operacion_s)
        except OSError as exc:
            return clasificar_error_http(exc, "portal_http")
        if r.status in (200, 302, 401):
            return ok(f"HTTP {r.status}: el Management Portal responde. La API no usa este puerto: "
                      "no prueba el Superserver")
        return fail(f"HTTP {r.status}", "El servidor web de IRIS respondió con error.", "Revisar IRIS_PORTAL_URL.")

    if not c.bloqueada_por:
        c.ejecutar("portal_http", "GET Management Portal", probar_portal, destino=portal)
    capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "IRIS_PORT")
    if not (capas & (NATIVAS | {"sonda"})):
        return
    try:
        import iris
    except ImportError:
        c.sin_herramienta("intersystems-irispython (Native API)")
        return

    def conectar(ns: str) -> object:
        return con_limite(
            lambda: iris.connect(host, puerto, ns, usuario, cfg.get("IRIS_PASSWORD"), timeout=int(conexion_s * 1000)),
            limite,
        )

    conexion = None
    conexion_sql = None
    try:
        # iris.connect resuelve protocolo, autenticación y namespace en una sola llamada:
        # el resultado se reparte por capa según el tipo de error.
        if c.bloqueada_por:
            c.ejecutar("protocolo", "handshake Superserver", lambda: ok("-"))
            c.ejecutar("autenticacion", f"login en {namespace}", lambda: ok("-"))
        else:
            inicio = time.perf_counter()
            try:
                conexion = conectar(namespace)
                ms = (time.perf_counter() - inicio) * 1000
                if c.activa("protocolo"):
                    c.registrar("protocolo", "handshake Superserver", ok("el Superserver completó el handshake"), ms)
                if c.activa("autenticacion"):
                    c.registrar("autenticacion", f"login en {namespace}",
                                ok(f"usuario '{usuario}' aceptado en el namespace '{namespace}'"), ms)
            except Exception as exc:  # noqa: BLE001 - se clasifica por capa
                ms = (time.perf_counter() - inicio) * 1000
                if "Access Denied" not in str(exc):
                    c.registrar("protocolo", "handshake Superserver", _clasificar(exc, "protocolo"), ms)
                else:
                    c.registrar("protocolo", "handshake Superserver",
                                ok("el Superserver respondió (rechazó el login: el protocolo funciona)"), ms)
                    _diferencial(c, conectar, alternativo, namespace, usuario, ms)
        nativo = iris.createIRIS(conexion) if conexion is not None else None

        def llamar(cls: str, metodo: str, *args: object) -> object:
            return con_limite(lambda: nativo.classMethodValue(cls, metodo, *args), operacion_s)

        def contexto() -> Paso:
            activo = llamar("%SYSTEM.SYS", "NameSpace")
            compilada = llamar("%Dictionary.CompiledClass", "%ExistsId", clase)
            if str(compilada) != "1":
                return fail(f"namespace '{activo}' sin la clase {clase} compilada",
                            "Namespace equivocado o falta compilar las clases del Hito 9.",
                            "Ejecutar scripts/preparar_datos.sh del Hito 10.")
            return ok(f"namespace activo '{activo}'; clase {clase} compilada")

        def seleccionar(codigo: str):
            nonlocal conexion_sql
            import iris.dbapi
            if conexion_sql is None:
                conexion_sql = con_limite(lambda: iris.dbapi.connect(
                    host, puerto, namespace, usuario, cfg.get("IRIS_PASSWORD"),
                    timeout=int(conexion_s * 1000)), limite)
            def consulta():
                cursor = conexion_sql.cursor()
                try:
                    cursor.execute("SELECT Codigo, Estado, Sede FROM Fixture.Partido WHERE Codigo = ?", [codigo])
                    return cursor.fetchall()
                finally:
                    cursor.close()
            return con_limite(consulta, operacion_s)

        def lectura() -> Paso:
            filas = seleccionar(acta)
            if not filas:
                return warn(f"SELECT del acta '{acta}' sin filas",
                            "La lectura funcionó pero el acta de prueba no existe (ausencia válida).",
                            "Revisar IRIS_ACTA_PRUEBA; la demostración del Hito 9 crea P-009.")
            return ok(f"SELECT parametrizado: acta '{filas[0][0]}', estado '{filas[0][1]}', sede '{filas[0][2]}'")

        c.ejecutar("autorizacion", "%SYSTEM.Version.GetNumber",
                   lambda: ok(f"Native API puede ejecutar métodos de clase: IRIS {llamar('%SYSTEM.Version', 'GetNumber')}"))
        c.ejecutar("contexto", "namespace + clase", contexto)
        c.ejecutar("lectura", "SELECT del acta (DB-API)", lectura)

        if sondas and c.activa("sonda") and c.bloqueada_por is None:
            def objeto_inexistente() -> Paso:
                if seleccionar("P-999"):
                    return fail("SELECT de 'P-999' devolvió filas",
                                "No se verificó una ausencia válida.", "Revisar el código de prueba.")
                return ok("SELECT de 'P-999' sin filas: ausencia de negocio (HTTP 404), no falla de conexión")

            def clase_inexistente() -> Paso:
                try:
                    llamar("Fixture.ClaseInexistenteH11", "X")
                except RuntimeError as exc:
                    if "<CLASS DOES NOT EXIST>" not in str(exc):
                        return _clasificar(exc, "sonda")
                    return ok(f"{str(exc).split('*')[0].strip()[:60]}: error de metadato, no de conexión")
                return fail("se esperaba <CLASS DOES NOT EXIST>", "Comportamiento inesperado.", "-")

            def namespace_incorrecto() -> Paso:
                existe = llamar("%SYS.Namespace", "Exists", "NOEXISTE_H11")
                if str(existe) != "0":
                    return fail("NOEXISTE_H11 existe", "No sirve como sonda de namespace inexistente.",
                                "Elegir un namespace que no exista.")
                return ok(f"%SYS.Namespace.Exists('NOEXISTE_H11') = {existe}: con un namespace inexistente "
                          "iris.connect devuelve 'Access Denied', igual que una credencial inválida; esta "
                          "consulta los distingue sin provocar logins fallidos")

            c.ejecutar("sonda", "objeto inexistente", objeto_inexistente)
            c.ejecutar("sonda", "clase inexistente", clase_inexistente)
            c.ejecutar("sonda", "namespace incorrecto", namespace_incorrecto)
    finally:
        if conexion_sql is not None:
            try:
                conexion_sql.close()
            except Exception:
                pass
        if conexion is not None:
            try:
                conexion.close()
            except Exception:  # noqa: BLE001 - la conexión puede estar rota
                pass


def _diferencial(c: Cadena, conectar, alternativo: str, namespace: str, usuario: str, ms: float) -> None:
    """'Access Denied': ¿credencial o namespace? Se reintenta en el namespace alternativo."""
    if alternativo == namespace:
        c.registrar("autenticacion", f"login en {namespace}", fail(
            "Access Denied",
            "Credencial inválida, usuario deshabilitado o sin permiso de login (IRIS no lo detalla).",
            "Revisar el usuario en el portal (Seguridad > Usuarios) y el log de auditoría; no reintentar "
            "contraseñas: los intentos fallidos deshabilitan la cuenta.",
        ), ms)
        return
    try:
        otra = conectar(alternativo)
    except Exception:  # noqa: BLE001 - la credencial tampoco sirve en el alternativo
        c.registrar("autenticacion", f"login en {namespace}", fail(
            f"Access Denied también en '{alternativo}'",
            "La credencial es inválida o el usuario está deshabilitado.",
            "Revisar IRIS_USER/IRIS_PASSWORD; no reintentar: los intentos fallidos deshabilitan la cuenta.",
        ), ms)
        return
    import iris

    try:
        existe = con_limite(lambda: iris.createIRIS(otra).classMethodValue("%SYS.Namespace", "Exists", namespace), 5)
    finally:
        otra.close()
    c.registrar("autenticacion", f"login en {alternativo}",
                ok(f"credencial válida para '{usuario}' (verificada en el namespace '{alternativo}')"), ms)
    c.registrar("contexto", f"namespace {namespace}", fail(
        f"namespace '{namespace}' {'inexistente' if str(existe) != '1' else 'sin permiso para el usuario'} "
        f"(%SYS.Namespace.Exists = {existe})",
        "La credencial funciona: el problema es el contexto. IRIS lo informa como 'Access Denied'.",
        "Corregir IRIS_NAMESPACE (USER en el laboratorio).",
    ), None)

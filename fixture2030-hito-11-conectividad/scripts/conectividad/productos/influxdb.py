"""InfluxDB 3 Core (Hito 8): estadísticas temporales. Cliente: API HTTP v3, como el adaptador (RF13).

| Capa          | Prueba                                        | Qué NO permite concluir                    |
|---------------|-----------------------------------------------|--------------------------------------------|
| protocolo     | GET /health sin token                         | Si el token configurado sirve              |
| autenticacion | GET /health con el token                      | Si el token tiene permiso de administración |
| autorizacion  | GET /api/v3/configure/database                | Si la database configurada existe          |
| contexto      | database + tabla en information_schema        | Si hay puntos en la ventana                |
| lectura       | COUNT y date_bin(5 min) en una ventana acotada | Rendimiento con ventanas grandes          |

El token nunca se imprime: solo se informa de dónde se leyó.
"""

from conectividad.config import Config, host_puerto
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red, clasificar_error_http, http
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, warn

NOMBRE = "influxdb"

SQL_CONTEO = (
    "SELECT COUNT(*) AS puntos, MIN(time) AS primero, MAX(time) AS ultimo FROM {tabla} "
    "WHERE partido_id = $partido AND time >= $desde AND time < $hasta"
)
SQL_AGREGADO = (
    "SELECT date_bin(INTERVAL '5 minutes', time) AS bloque, AVG(posesion_pct) AS posesion_prom "
    "FROM {tabla} WHERE partido_id = $partido AND time >= $desde AND time < $hasta "
    "GROUP BY 1 ORDER BY 1 LIMIT 50"
)


def _clasificar(exc: BaseException, capa: str) -> Paso:
    if isinstance(exc, OSError):
        return clasificar_error_http(exc, capa)
    return clasificar_generico(exc, capa)


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    url = cfg.get("INFLUX_URL").rstrip("/")
    host, puerto = host_puerto(url, 8181)
    database, tabla = cfg.get("INFLUX_DATABASE"), cfg.get("INFLUX_TABLA")
    partido, desde, hasta = cfg.get("INFLUX_PARTIDO_PRUEBA"), cfg.get("INFLUX_DESDE"), cfg.get("INFLUX_HASTA")
    operacion_s = cfg.decimal("TIMEOUT_OPERACION_S")
    token, origen_token = cfg.token_influx()
    c = Cadena(registro, NOMBRE, capas, f"{url} database={database}", _clasificar)

    capa_configuracion(c, cfg, ["INFLUX_URL", "INFLUX_DATABASE", "INFLUX_TOKEN", "INFLUX_TOKEN_FILE"],
                       ["INFLUX_URL", "INFLUX_DATABASE"])
    if c.activa("configuracion") and not c.bloqueada_por and not token:
        c.registrar("configuracion", "origen del token", Paso(
            "WARN", f"no hay token: {origen_token} -> producto no configurado",
            "Sin token no se puede pasar de la capa de protocolo.",
            "Definir INFLUX_TOKEN o generar el archivo con fixture2030-influxDB/scripts/inicializacion.sh.",
            datos={"no_configurado": True}), None)
        c.bloquear("configuracion", "no ejecutada: falta el token de InfluxDB")
    elif c.activa("configuracion") and not c.bloqueada_por:
        c.registrar("configuracion", "origen del token", ok(f"token leído de {origen_token} (valor oculto)"), None)
    capa_contenedor(c, cfg, "influxdb")
    capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "INFLUX_URL")
    if not (capas & (NATIVAS | {"sonda"})):
        return

    autorizacion_hdr = {"Authorization": f"Bearer {token}"}

    def consulta(sql: str, db: str = database, cabeceras: dict | None = None) -> tuple[int, object]:
        # Valores siempre como parámetros ($partido, ...), nunca concatenados en el SQL.
        params = {"partido": partido, "desde": desde, "hasta": hasta} if "$" in sql else {}
        r = http("POST", f"{url}/api/v3/query_sql", operacion_s, headers=cabeceras or autorizacion_hdr,
                 cuerpo_json={"db": db, "q": sql.format(tabla=tabla), "params": params, "format": "json"})
        try:
            return r.status, r.json()
        except ValueError:
            return r.status, r.cuerpo[:120].decode(errors="replace")

    def protocolo() -> Paso:
        r = http("GET", f"{url}/health", operacion_s)
        version = r.headers.get("x-influxdb-version", "")
        if r.status == 200:
            return ok(f"sin token -> 200 {r.cuerpo[:20].decode(errors='replace')} {version}".strip())
        if r.status == 401:
            return ok("sin token -> 401: el servicio HTTP responde y exige token también en /health "
                      "(InfluxDB 3 Core con autorización activa)")
        return fail(f"GET /health -> HTTP {r.status}", "Respuesta HTTP inesperada (¿otro servicio en el puerto?).",
                    "Verificar INFLUX_URL.")

    def autenticacion() -> Paso:
        r = http("GET", f"{url}/health", operacion_s, headers=autorizacion_hdr)
        if r.status == 200:
            return ok(f"con token -> 200 {r.cuerpo[:20].decode(errors='replace')} "
                      f"(token de {origen_token})")
        if r.status == 401:
            return fail("token rechazado (401)", "El token no existe en este servidor (se regeneró o es de otra instancia).",
                        "Regenerar con inicializacion.sh del Hito 8 y actualizar el archivo de token.")
        return fail(f"GET /health con token -> HTTP {r.status}", "Respuesta inesperada.", "Revisar logs de InfluxDB.")

    def autorizacion() -> Paso:
        r = http("GET", f"{url}/api/v3/configure/database?format=json", operacion_s, headers=autorizacion_hdr)
        if r.status == 200:
            nombres = [d.get("iox::database") for d in (r.json() or [])]
            return ok(f"listado de databases permitido: {', '.join(n for n in nombres if n)}", valor=nombres)
        if r.status == 403:
            return warn("el token no puede listar databases (403): token de recurso, no de administración",
                        "La API solo necesita consultar; se verifica el contexto con una consulta.", "-", valor=[])
        return fail(f"GET /api/v3/configure/database -> HTTP {r.status}", "El token no tiene acceso.",
                    "Usar un token con permiso sobre la database.")

    def contexto(nombres: list | None) -> Paso:
        if nombres and database not in nombres:
            return fail(
                f"database '{database}' inexistente (existen: {', '.join(nombres)})",
                "El servicio y el token funcionan; INFLUX_DATABASE apunta a otra base.",
                "Corregir INFLUX_DATABASE o crear la base con inicializacion.sh del Hito 8.",
            )
        status, filas = consulta("SELECT table_name FROM information_schema.tables WHERE table_name = '{tabla}'")
        if status == 404:
            return fail(f"database '{database}' inexistente (404)", "INFLUX_DATABASE incorrecta.",
                        "Corregir INFLUX_DATABASE.")
        if status != 200:
            return fail(f"information_schema -> HTTP {status}: {filas}", "Consulta rechazada.", "Revisar el token.")
        if not filas:
            return fail(f"tabla '{tabla}' inexistente en '{database}'", "No se cargaron las estadísticas del Hito 8.",
                        "Ejecutar scripts/datos/cargar_estadisticas_influx.py del Hito 10.")
        return ok(f"database '{database}' con la tabla '{tabla}'")

    def lectura() -> Paso:
        status, filas = consulta(SQL_CONTEO)
        if status != 200:
            return fail(f"consulta acotada -> HTTP {status}: {filas}", "La consulta fue rechazada.", "Revisar SQL y token.")
        fila = (filas or [{}])[0]
        rango = f"partido {partido}, [{desde}, {hasta})"
        if not fila.get("puntos"):
            return warn(f"COUNT(*) = 0 en {rango}",
                        "La consulta funcionó: no hay puntos en la ventana (ausencia válida, no caída).",
                        "Revisar INFLUX_DESDE/INFLUX_HASTA o la carga del Hito 8.")
        return ok(f"COUNT(*) = {fila['puntos']} en {rango} (primero {fila['primero']}, último {fila['ultimo']})")

    def agregacion() -> Paso:
        status, filas = consulta(SQL_AGREGADO)
        if status != 200:
            return fail(f"date_bin -> HTTP {status}: {filas}", "La agregación fue rechazada.", "Revisar SQL.")
        promedios = ", ".join(f"{f['posesion_prom']:.1f}" for f in filas or [])
        return ok(f"date_bin(5 min) + AVG(posesion_pct): {len(filas or [])} bloques [{promedios}]")

    c.ejecutar("protocolo", "GET /health (sin token)", protocolo)
    c.ejecutar("autenticacion", "GET /health (con token)", autenticacion)
    nombres = c.ejecutar("autorizacion", "listar databases", autorizacion)
    c.ejecutar("contexto", "database + tabla", lambda: contexto(nombres))
    c.ejecutar("lectura", "COUNT acotado por tiempo", lectura)
    c.ejecutar("lectura", "agregación date_bin", agregacion)

    if sondas and c.activa("sonda") and c.bloqueada_por is None:
        def token_invalido() -> Paso:
            r = http("GET", f"{url}/api/v3/configure/database?format=json", operacion_s,
                     headers={"Authorization": "Bearer token-invalido-de-diagnostico"})
            if r.status != 401:
                return fail(f"token inválido -> HTTP {r.status}; se esperaba 401",
                            "No se comprobó el rechazo de la identidad; un 200 no demuestra autenticación activa.",
                            "Verificar la configuración de autorización y el endpoint de prueba.")
            return ok("token inválido -> HTTP 401: autenticación rechazada, servicio accesible")

        def database_inexistente() -> Paso:
            status, cuerpo = consulta("SELECT 1", db="fixture2030_inexistente_h11")
            if status != 404 or "database" not in str(cuerpo).lower() or "not found" not in str(cuerpo).lower():
                return fail(f"database inexistente -> HTTP {status}: {str(cuerpo)[:120]}",
                            "No se comprobó un error de database inexistente.",
                            "Revisar el contexto, el token y el mensaje de la respuesta.")
            return ok(f"database inexistente -> HTTP {status} {str(cuerpo)[:70]}: error de contexto")

        def sin_puntos() -> Paso:
            r = http("POST", f"{url}/api/v3/query_sql", operacion_s, headers=autorizacion_hdr, cuerpo_json={
                "db": database, "q": SQL_CONTEO.format(tabla=tabla), "format": "json",
                "params": {"partido": partido, "desde": "2031-01-01T00:00:00Z", "hasta": "2031-01-01T01:00:00Z"}})
            if r.status != 200:
                return fail(f"ventana sin puntos -> HTTP {r.status}", "La consulta no terminó correctamente.",
                            "Verificar contexto y token; una consulta rechazada no demuestra ausencia de puntos.")
            filas = r.json()
            if not isinstance(filas, list) or not filas or filas[0].get("puntos") != 0:
                return fail("la ventana no devolvió COUNT(*) = 0", "No se verificó la ausencia de puntos.",
                            "Seleccionar una ventana sin datos y repetir.")
            fila = filas[0]
            return ok(f"ventana 2031-01-01 sin datos -> HTTP {r.status}, COUNT(*) = {fila.get('puntos')}: "
                      "ausencia de puntos válida (la API responde 200 con series vacías)")

        c.ejecutar("sonda", "token inválido", token_invalido)
        c.ejecutar("sonda", "database inexistente", database_inexistente)
        c.ejecutar("sonda", "ventana sin puntos", sin_puntos)

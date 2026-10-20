"""Redis (Hito 7): sesiones y caché. Cliente: redis-py, el mismo de la API (RF12).

| Capa          | Prueba                                   | Qué NO permite concluir                         |
|---------------|------------------------------------------|-------------------------------------------------|
| protocolo     | PING mediante redis-py                   | Si la credencial es válida                      |
| autenticacion | conexión del cliente + ACL WHOAMI        | Permisos sobre las claves                       |
| autorizacion  | DBSIZE (comando de lectura del keyspace) | Si la base lógica es la correcta                |
| contexto      | CLIENT INFO (db) + INFO keyspace         | Si existe la clave de prueba                    |
| lectura       | EXISTS / TYPE / PTTL de la clave de prueba | Ausente y expirada se ven igual (TTL -2)      |

La sonda de expiración escribe una clave `diag:h11:<uuid>` con 1,5 s de vida.
No es dato de dominio y se autodestruye, pero es una escritura: está
desactivada salvo REDIS_SONDA_EXPIRACION=1.
"""

import time
import uuid

from conectividad.config import Config
from conectividad.productos.comun import capa_configuracion, capa_contenedor, clasificar_generico
from conectividad.red import capa_red, puerto_cerrado
from conectividad.registro import NATIVAS, Cadena, Paso, Registro, fail, ok, resumen_excepcion, skip, warn

NOMBRE = "redis"


def _clasificar(exc: BaseException, capa: str) -> Paso:
    from redis import exceptions as e

    if isinstance(exc, e.AuthenticationError):
        return fail("credencial rechazada (AUTH)", "REDIS_PASSWORD no coincide con requirepass/ACL.",
                    "Verificar REDIS_PASSWORD.")
    if isinstance(exc, e.NoPermissionError):
        return fail("identidad sin permiso (NOPERM)", "El usuario ACL no puede ejecutar el comando.",
                    "Revisar ACL LIST.")
    if isinstance(exc, e.BusyLoadingError):
        return fail("Redis cargando el dataset (LOADING)", "El servidor arrancó y todavía lee el AOF/RDB.",
                    "Esperar y repetir; no es una falla de red.")
    if isinstance(exc, e.TimeoutError):
        return fail("timeout", "El servidor no respondió dentro del límite.", "Revisar carga y red.")
    if isinstance(exc, e.ResponseError) and "DB index" in str(exc):
        return fail(f"base lógica inválida ({exc})", "REDIS_DB fuera de rango (databases del servidor).",
                    "Corregir REDIS_DB.")
    if isinstance(exc, e.ConnectionError):
        return fail(f"conexión fallida ({resumen_excepcion(exc, 90)})", "No hay servidor Redis aceptando.",
                    "Revisar la capa TCP y el contenedor.")
    return clasificar_generico(exc, capa)


def evaluar(cfg: Config, registro: Registro, capas: set[str], sondas: bool) -> None:
    host, puerto, db = cfg.get("REDIS_HOST"), cfg.entero("REDIS_PORT"), cfg.entero("REDIS_DB")
    clave = cfg.get("REDIS_CLAVE_PRUEBA")
    conexion_s, operacion_s = cfg.decimal("TIMEOUT_CONEXION_S"), cfg.decimal("TIMEOUT_OPERACION_S")
    c = Cadena(registro, NOMBRE, capas, f"{host}:{puerto} db={db}", _clasificar)

    capa_configuracion(c, cfg, ["REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB", "REDIS_CLAVE_PRUEBA"],
                       ["REDIS_HOST", "REDIS_PORT", "REDIS_DB"])
    capa_contenedor(c, cfg, "redis")
    capa_red(c, host, puerto, cfg.decimal("TCP_TIMEOUT_S"), "REDIS_PORT")
    if not (capas & (NATIVAS | {"sonda"})):
        return
    try:
        import redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry
    except ImportError:
        c.sin_herramienta("redis-py")
        return

    def cliente(port: int = puerto) -> "redis.Redis":
        return redis.Redis(
            host=host, port=port, db=db, password=cfg.get("REDIS_PASSWORD") or None,
            socket_connect_timeout=conexion_s, socket_timeout=operacion_s,
            retry=Retry(NoBackoff(), 0), decode_responses=True, client_name="fixture2030-diagnostico-h11",
        )

    r = cliente()
    anonimo = redis.Redis(host=host, port=puerto, db=0, socket_connect_timeout=conexion_s,
                          socket_timeout=operacion_s, retry=Retry(NoBackoff(), 0))
    try:
        def protocolo() -> Paso:
            try:
                if not anonimo.ping():
                    return fail("PING no devolvió PONG", "Respuesta inesperada.", "Revisar REDIS_PORT.")
            except (redis.exceptions.AuthenticationError, redis.exceptions.NoPermissionError):
                return ok("el servidor respondió RESP y exige identidad o permisos; todavía no valida la credencial")
            return ok("PING mediante redis-py -> PONG (sin credenciales)")

        c.ejecutar("protocolo", "PING (redis-py)", protocolo)

        def autenticacion() -> Paso:
            usuario = r.execute_command("ACL WHOAMI")
            if cfg.get("REDIS_PASSWORD"):
                return ok(f"AUTH aceptado; usuario ACL '{usuario}'")
            return ok(f"sin contraseña configurada; el servidor acepta la conexión como '{usuario}' (laboratorio)")

        def contexto() -> Paso:
            info = r.client_info()
            espacio = r.info("keyspace").get(f"db{db}", {"keys": 0, "expires": 0})
            version = r.info("server").get("redis_version")
            return ok(f"Redis {version}; base lógica db={info.get('db')}: {espacio['keys']} claves, "
                      f"{espacio['expires']} con TTL")

        def lectura() -> Paso:
            pipe = r.pipeline(transaction=False)
            pipe.exists(clave)
            pipe.type(clave)
            pipe.pttl(clave)
            existe, tipo, pttl = pipe.execute()
            if existe and pttl > 0:
                return ok(f"'{clave}' ({tipo}) presente; expira en {pttl / 1000:.0f} s")
            if existe:
                return ok(f"'{clave}' ({tipo}) presente sin expiración (TTL -1)")
            return warn(
                f"'{clave}' ausente o expirada: EXISTS 0, PTTL {pttl}",
                "Redis respondió normalmente: la clave no existe (nunca se cargó o ya venció su TTL). "
                "Ausente y expirada se ven igual (-2); ninguna de las dos es 'Redis caído'.",
                "Recargar fixture2030-redis/scripts/carga_muestra.redis si se necesita la sesión de prueba.",
            )

        c.ejecutar("autenticacion", "ACL WHOAMI", autenticacion)
        c.ejecutar("autorizacion", "DBSIZE", lambda: ok(f"permitido: {r.dbsize()} claves en la base lógica"))
        c.ejecutar("contexto", "CLIENT INFO + INFO keyspace", contexto)
        c.ejecutar("lectura", "EXISTS/TYPE/PTTL", lectura)

        if sondas and c.activa("sonda") and c.bloqueada_por is None:
            ausente = f"diag:h11:inexistente:{uuid.uuid4().hex[:8]}"
            c.ejecutar("sonda", "clave ausente", lambda: ok(
                f"EXISTS {ausente} = {r.exists(ausente)}, PTTL = {r.pttl(ausente)}: ausencia válida (nil), "
                "no es error"))

            def expiracion() -> Paso:
                if cfg.get("REDIS_SONDA_EXPIRACION") != "1":
                    return skip("desactivada (REDIS_SONDA_EXPIRACION=0): escribe una clave diag: de 1,5 s")
                temporal = f"diag:h11:expira:{uuid.uuid4().hex[:8]}"
                if not r.set(temporal, "1", px=1500, nx=True):
                    return fail("no se creó la clave temporal", "La clave ya existía.", "Repetir con otra clave.")
                antes = r.pttl(temporal)
                time.sleep(1.7)
                existe, despues = r.exists(temporal), r.pttl(temporal)
                if not (0 < antes <= 1500 and existe == 0 and despues == -2):
                    return fail(f"expiración no verificada: PTTL inicial={antes}, EXISTS={existe}, PTTL final={despues}",
                                "No se observó la transición esperada.", "Repetir y revisar el TTL.")
                return ok(f"{temporal}: PTTL {antes} ms -> tras 1,7 s EXISTS {existe}, PTTL {despues}. "
                          "Expirada se lee igual que ausente; solo el TTL observado antes las distingue")

            def no_disponible() -> Paso:
                libre = puerto_cerrado()
                otro = cliente(libre)
                inicio = time.perf_counter()
                try:
                    otro.ping()
                except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as exc:
                    ms = (time.perf_counter() - inicio) * 1000
                    nota = (" En Windows el rechazo en 127.0.0.1 tarda ~2 s (reintentos de SYN): con "
                            "TIMEOUT_CONEXION_S=2 la caída se informa como timeout (504)."
                            if isinstance(exc, redis.exceptions.TimeoutError) else "")
                    return ok(f"127.0.0.1:{libre} sin servidor -> {type(exc).__name__} en {ms:.0f} ms: excepción, "
                              f"distinta de nil (la API responde 503/504, nunca 404).{nota}")
                finally:
                    otro.close()
                return fail("se esperaba ConnectionError", "Había un servidor en el puerto.", "-")

            c.ejecutar("sonda", "clave expirada", expiracion)
            c.ejecutar("sonda", "Redis no disponible", no_disponible)
    finally:
        anonimo.close()
        r.close()

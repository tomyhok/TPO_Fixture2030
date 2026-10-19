"""Capas de resolución, TCP y HTTP, solo con la biblioteca estándar (RF4, RF5, sección 5.3).

Este módulo no necesita ningún driver: el modo `--modo tcp` funciona aunque no
esté instalado ningún cliente de base de datos.
"""

import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from conectividad.registro import Cadena, Paso, fail, ok, warn


class LimiteExcedido(Exception):
    """La operación no terminó dentro del límite de espera del diagnóstico."""


def con_limite(fn: Callable[[], Any], segundos: float) -> Any:
    """Ejecuta `fn` en un hilo y corta la espera en `segundos` (RNF5).

    Para clientes sin timeout propio por operación (IRIS): el hilo queda
    abandonado como daemon y no bloquea el fin del diagnóstico.
    """
    resultado: dict[str, Any] = {}

    def correr() -> None:
        try:
            resultado["valor"] = fn()
        except BaseException as exc:  # noqa: BLE001 - se re-lanza en el hilo principal
            resultado["error"] = exc

    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        raise LimiteExcedido(f"sin respuesta en {segundos:g} s")
    if "error" in resultado:
        raise resultado["error"]
    return resultado.get("valor")


def puerto_cerrado(host: str = "127.0.0.1") -> int:
    """Un puerto local sin listener (se reserva y se libera), para sondas de 'no disponible'."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


# --------------------------------------------------------------- resolución
def _es_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def resolver(host: str, puerto: int) -> Paso:
    if _es_ip(host):
        return ok(f"'{host}' es una dirección IP literal: no requiere DNS", valor=[host])
    try:
        infos = socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return fail(
            f"host '{host}' no resuelto ({exc.strerror or exc})",
            "El nombre no existe en este entorno. Un nombre de servicio de Docker Compose "
            "(mongodb, neo4j, ...) solo resuelve dentro de la red de Compose, no en la notebook.",
            "Desde la notebook usar 127.0.0.1 y el puerto publicado; desde un contenedor usar el "
            "nombre del servicio y ejecutar el diagnóstico en esa misma red.",
        )
    direcciones = list(dict.fromkeys(info[4][0] for info in infos))
    detalle = f"'{host}' -> {', '.join(direcciones)}"
    if host == "localhost" and direcciones and ":" in direcciones[0]:
        return warn(
            detalle,
            "localhost resuelve primero a IPv6 (::1). Si el puerto solo está publicado en IPv4, "
            "cada conexión fallida espera el timeout dos veces.",
            "Preferir 127.0.0.1 en la configuración de la notebook.",
            valor=direcciones,
        )
    return ok(detalle, valor=direcciones)


# --------------------------------------------------------------------- TCP
@dataclass
class ResultadoTCP:
    clase: str  # ok | refused | timeout | error
    direccion: str
    detalle: str


def conectar_tcp(direccion: str, puerto: int, timeout_s: float) -> ResultadoTCP:
    familia = socket.AF_INET6 if ":" in direccion else socket.AF_INET
    with socket.socket(familia, socket.SOCK_STREAM) as s:
        s.settimeout(timeout_s)
        inicio = time.perf_counter()
        try:
            s.connect((direccion, puerto))
            return ResultadoTCP("ok", direccion, "listener aceptó la conexión")
        except ConnectionRefusedError:
            ms = (time.perf_counter() - inicio) * 1000
            nota = " (Windows reintenta el SYN: el rechazo local tarda ~2 s)" if ms > 1000 else ""
            return ResultadoTCP("refused", direccion, f"connection refused tras {ms:.0f} ms{nota}")
        except (TimeoutError, socket.timeout):
            return ResultadoTCP("timeout", direccion, f"timeout tras {timeout_s:g} s sin respuesta")
        except OSError as exc:
            return ResultadoTCP("error", direccion, f"error de red: {exc.strerror or exc}")


def probar_tcp(direcciones: list[str], puerto: int, timeout_s: float, variable_puerto: str) -> Paso:
    intentos = [conectar_tcp(d, puerto, timeout_s) for d in direcciones]
    exito = next((i for i in intentos if i.clase == "ok"), None)
    if exito:
        extra = ""
        fallidos = [i for i in intentos if i.clase != "ok"]
        if fallidos:
            extra = f" (antes falló {fallidos[0].direccion}: {fallidos[0].detalle})"
        return ok(f"{exito.direccion}:{puerto} {exito.detalle}{extra}", valor=exito.direccion)
    peor = intentos[0]
    if peor.clase == "refused":
        return fail(
            f"{peor.direccion}:{puerto} {peor.detalle}",
            "El host responde pero nadie escucha en ese puerto: contenedor detenido, puerto no "
            "publicado o puerto equivocado. Un contenedor 'Up' no garantiza que este puerto esté publicado.",
            f"docker ps -a / docker port <contenedor>; verificar {variable_puerto} contra el compose.",
            clase_tcp="refused",
        )
    if peor.clase == "timeout":
        return fail(
            f"{peor.direccion}:{puerto} {peor.detalle}",
            "Sin respuesta dentro del límite: firewall, ruta inexistente, host equivocado o servicio saturado.",
            "Repetir desde el mismo entorno con TCP_TIMEOUT_S mayor y revisar la red de Docker.",
            clase_tcp="timeout",
        )
    return fail(
        f"{peor.direccion}:{puerto} {peor.detalle}",
        "El sistema operativo rechazó la conexión antes de llegar al servidor (dirección inválida o red caída).",
        "Revisar el host configurado y la red local.",
        clase_tcp="error",
    )


def capa_red(cadena: Cadena, host: str, puerto: int, timeout_s: float, variable_puerto: str) -> str | None:
    """Ejecuta resolución + TCP y devuelve la dirección que aceptó la conexión."""
    destino = f"{host}:{puerto}"
    direcciones = cadena.ejecutar("resolucion", "getaddrinfo", lambda: resolver(host, puerto), destino)
    # Si la resolución falló, la cadena queda bloqueada y TCP se registra como SKIP.
    # Si no se pidió la capa de resolución, connect() resuelve el nombre por su cuenta.
    lista = direcciones if direcciones is not None else [host]
    return cadena.ejecutar(
        "tcp", "connect()", lambda: probar_tcp(lista, puerto, timeout_s, variable_puerto), destino
    )


# -------------------------------------------------------------------- HTTP
@dataclass
class RespuestaHTTP:
    status: int
    headers: dict[str, str]
    cuerpo: bytes
    duracion_ms: float

    def json(self) -> Any:
        return json.loads(self.cuerpo.decode("utf-8")) if self.cuerpo else None


def http(
    metodo: str,
    url: str,
    timeout_s: float,
    headers: dict[str, str] | None = None,
    cuerpo_json: Any = None,
) -> RespuestaHTTP:
    """GET/POST con timeout. Los 4xx/5xx se devuelven como respuesta, no como excepción."""
    datos = None
    headers = dict(headers or {})
    if cuerpo_json is not None:
        datos = json.dumps(cuerpo_json).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    pedido = urllib.request.Request(url, data=datos, method=metodo, headers=headers)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(pedido, timeout=timeout_s) as r:  # noqa: S310 - URL de configuración
            cuerpo = r.read()
            status, cabeceras = r.status, dict(r.headers.items())
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read()
        status, cabeceras = exc.code, dict(exc.headers.items())
    return RespuestaHTTP(status, {k.lower(): v for k, v in cabeceras.items()}, cuerpo,
                         (time.perf_counter() - inicio) * 1000)


def clasificar_error_http(exc: BaseException, capa: str) -> Paso:
    """Errores de transporte de urllib (sin respuesta HTTP)."""
    razon = getattr(exc, "reason", exc)
    if isinstance(razon, (TimeoutError, socket.timeout)) or isinstance(exc, (TimeoutError, socket.timeout)):
        return fail(
            "timeout esperando la respuesta HTTP",
            "El servicio aceptó la conexión pero no respondió a tiempo (arranque, saturación o puerto de otro protocolo).",
            "Repetir con un timeout mayor; revisar los logs del contenedor.",
        )
    if isinstance(razon, ConnectionRefusedError):
        return fail(
            "connection refused",
            "No hay listener HTTP en ese host y puerto.",
            "Verificar que el servicio esté iniciado y el puerto publicado.",
        )
    if isinstance(razon, socket.gaierror):
        return fail(
            f"host no resuelto ({razon})",
            "El nombre del host no existe en este entorno.",
            "Usar el host correcto para el entorno de ejecución.",
        )
    return fail(
        f"error HTTP sin respuesta: {type(exc).__name__}: {razon}"[:200],
        "El listener no respondió con HTTP válido (puerto de otro protocolo o conexión cortada).",
        "Verificar que la URL apunte al puerto HTTP del producto.",
    )

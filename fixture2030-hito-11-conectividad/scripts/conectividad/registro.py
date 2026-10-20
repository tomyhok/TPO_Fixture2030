"""Resultados, redacción de secretos, cadena de capas y matriz de conectividad.

Estados de una prueba:
  OK    la prueba concreta funcionó (no garantiza rendimiento ni disponibilidad futura);
  WARN  funcionó con una observación que hay que leer (p. ej. dato de prueba ausente);
  FAIL  se intentó y falló: va acompañada de hipótesis y siguiente paso (RNF10);
  SKIP  no se ejecutó por falta de herramienta, de configuración o porque falló una
        capa previa. SKIP no significa "producto caído".
"""

import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, TextIO

OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"

# Capas de la cadena que usa la API, de menor a mayor costo (sección 5.2).
CAPAS = (
    "configuracion",
    "resolucion",
    "tcp",
    "protocolo",
    "autenticacion",
    "autorizacion",
    "contexto",
    "lectura",
)
NATIVAS = set(CAPAS[3:])
# Pruebas complementarias: informan, pero no bloquean la cadena.
SECUNDARIAS = ("contenedor", "portal_http", "sonda", "api", "diagnostico")
ABREVIATURA = {
    "configuracion": "Cfg",
    "resolucion": "DNS",
    "tcp": "TCP",
    "protocolo": "Prot",
    "autenticacion": "AuthN",
    "autorizacion": "AuthZ",
    "contexto": "Ctx",
    "lectura": "Lect",
}

ESTADOS_PRODUCTO = ("disponible", "degradado", "no disponible", "desconocido", "no probado", "no configurado")


def ahora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ redacción
class Redactor:
    """Oculta secretos conocidos y patrones de credenciales en todo texto de salida (RNF8)."""

    _URI = re.compile(r"(\b[a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@", re.IGNORECASE)
    _BEARER = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)
    _CLAVE = re.compile(r"((?:password|passwd|pwd|token|secret)=)[^\s&;,]+", re.IGNORECASE)
    _JSON = re.compile(r'("(?:password|token|secret)"\s*:\s*")[^"]*"', re.IGNORECASE)
    # Carpeta personal (C:/Users/<nombre>, /c/Users/<nombre>, /home/<nombre>): dato personal (RNF7).
    _HOME = re.compile(r"(?:\b[A-Za-z]:[\\/]+|/[a-z]/|/)(?:Users|home)[\\/]+[^\\/\s\"']+", re.IGNORECASE)

    def __init__(self, secretos: list[str]):
        self._secretos = sorted({s for s in secretos if s}, key=len, reverse=True)

    def __call__(self, texto: str) -> str:
        for secreto in self._secretos:
            texto = texto.replace(secreto, "***")
        texto = self._URI.sub(r"\1\2:***@", texto)
        texto = self._BEARER.sub(r"\1***", texto)
        texto = self._JSON.sub(r'\1***"', texto)
        texto = self._HOME.sub("~", texto)
        return self._CLAVE.sub(r"\1***", texto)


# ------------------------------------------------------------------ modelos
@dataclass
class Paso:
    estado: str
    detalle: str
    hipotesis: str = ""
    siguiente_paso: str = ""
    valor: Any = None
    datos: dict[str, Any] = field(default_factory=dict)


def ok(detalle: str, valor: Any = None, **datos: Any) -> Paso:
    return Paso(OK, detalle, valor=valor, datos=datos)


def warn(detalle: str, hipotesis: str = "", siguiente: str = "", valor: Any = None, **datos: Any) -> Paso:
    return Paso(WARN, detalle, hipotesis, siguiente, valor=valor, datos=datos)


def fail(detalle: str, hipotesis: str, siguiente: str, **datos: Any) -> Paso:
    return Paso(FAIL, detalle, hipotesis, siguiente, datos=datos)


def skip(detalle: str) -> Paso:
    return Paso(SKIP, detalle)


@dataclass
class Resultado:
    producto: str
    capa: str
    prueba: str
    estado: str
    detalle: str
    destino: str
    instante: str
    duracion_ms: float | None = None
    hipotesis: str = ""
    siguiente_paso: str = ""
    datos: dict[str, Any] = field(default_factory=dict)


def resumen_excepcion(exc: BaseException, largo: int = 160) -> str:
    texto = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {texto[:largo]}" if texto else type(exc).__name__


# ------------------------------------------------------------------ registro
class Registro:
    def __init__(self, redactor: Redactor, salida: TextIO | None = None, umbral_lento_ms: float = 1000.0):
        self.redactor = redactor
        self.salida = sys.stdout if salida is None else salida
        self.umbral_lento_ms = umbral_lento_ms
        self.resultados: list[Resultado] = []

    def escribir(self, texto: str = "") -> None:
        print(self.redactor(texto), file=self.salida, flush=True)

    def agregar(self, resultado: Resultado) -> Resultado:
        if (resultado.capa == "lectura" and resultado.estado == OK and resultado.duracion_ms
                and resultado.duracion_ms > self.umbral_lento_ms):
            resultado.estado = WARN
            resultado.hipotesis = (f"La lectura funcionó pero tardó más que UMBRAL_LENTO_MS ({self.umbral_lento_ms:g} ms): "
                                   "dependencia degradada para este origen y momento.")
            resultado.siguiente_paso = "Repetir; si persiste, revisar carga del producto (base para el Hito 12)."
            resultado.datos["degrada"] = True
        r = self.redactor
        resultado.detalle = r(resultado.detalle)
        resultado.destino = r(resultado.destino)
        resultado.hipotesis = r(resultado.hipotesis)
        resultado.siguiente_paso = r(resultado.siguiente_paso)
        resultado.datos = {k: (r(v) if isinstance(v, str) else v) for k, v in resultado.datos.items()}
        self.resultados.append(resultado)
        ms = f"{resultado.duracion_ms:8.1f} ms" if resultado.duracion_ms is not None else " " * 11
        self.escribir(
            f"[{resultado.estado:<4}] {resultado.producto:<9} {resultado.capa:<13} {ms}  "
            f"{resultado.prueba}: {resultado.detalle}"
        )
        if resultado.estado == FAIL:
            self.escribir(f"{'':>8}hipótesis: {resultado.hipotesis}")
            self.escribir(f"{'':>8}siguiente paso: {resultado.siguiente_paso}")
        elif resultado.estado == WARN and resultado.hipotesis:
            self.escribir(f"{'':>8}observación: {resultado.hipotesis}")
        return resultado

    def conteo(self) -> dict[str, int]:
        cuenta = {OK: 0, WARN: 0, FAIL: 0, SKIP: 0}
        for r in self.resultados:
            cuenta[r.estado] += 1
        return cuenta

    def como_dict(self) -> list[dict[str, Any]]:
        return [asdict(r) for r in self.resultados]


# ------------------------------------------------------------------ cadena
class Cadena:
    """Ejecuta las pruebas de un producto en orden de costo creciente.

    Si una capa de la cadena falla, las capas siguientes se registran como SKIP
    ("no evaluada") en lugar de ejecutarse: así el diagnóstico apunta a la
    primera capa rota y no se acumulan errores derivados. Las pruebas
    secundarias (contenedor, portal HTTP, sondas) nunca bloquean la cadena.
    """

    def __init__(
        self,
        registro: Registro,
        producto: str,
        capas: set[str],
        destino: str,
        clasificar: Callable[[BaseException, str], Paso],
    ):
        self.registro = registro
        self.producto = producto
        self.capas = capas
        self.destino = destino
        self.clasificar = clasificar
        self.bloqueada_por: str | None = None
        self.motivo_bloqueo = ""

    def activa(self, capa: str) -> bool:
        return capa in self.capas

    def registrar(self, capa: str, prueba: str, paso: Paso, duracion_ms: float | None, destino: str | None = None) -> None:
        self.registro.agregar(
            Resultado(
                producto=self.producto,
                capa=capa,
                prueba=prueba,
                estado=paso.estado,
                detalle=paso.detalle,
                destino=destino or self.destino,
                instante=ahora(),
                duracion_ms=None if duracion_ms is None else round(duracion_ms, 1),
                hipotesis=paso.hipotesis,
                siguiente_paso=paso.siguiente_paso,
                datos=paso.datos,
            )
        )
        if paso.estado == FAIL and capa in CAPAS and self.bloqueada_por is None:
            self.bloquear(capa, f"falló la capa '{capa}'")

    def bloquear(self, capa: str, motivo: str) -> None:
        self.bloqueada_por = capa
        self.motivo_bloqueo = motivo

    def ejecutar(self, capa: str, prueba: str, fn: Callable[[], Paso], destino: str | None = None) -> Any:
        """Corre una prueba y devuelve `paso.valor` si terminó en OK/WARN, o None."""
        if not self.activa(capa):
            return None
        if self.bloqueada_por and capa in CAPAS:
            self.registrar(capa, prueba, skip(f"no evaluada: {self.motivo_bloqueo}"), None, destino)
            return None
        inicio = time.perf_counter()
        try:
            paso = fn()
        except Exception as exc:  # noqa: BLE001 - toda excepción se clasifica, nunca se oculta
            paso = self.clasificar(exc, capa)
        self.registrar(capa, prueba, paso, (time.perf_counter() - inicio) * 1000, destino)
        return paso.valor if paso.estado in (OK, WARN) else None

    def sin_herramienta(self, herramienta: str, capas: tuple[str, ...] = tuple(NATIVAS) + ("sonda",)) -> None:
        """Registra SKIP en las capas que necesitaban un cliente no instalado."""
        for capa in CAPAS + ("sonda",):
            if capa in capas and self.activa(capa):
                self.registrar(capa, "cliente nativo", skip(f"{herramienta} no está instalado en este entorno"), None)


# ------------------------------------------------------------------ matriz
def estado_producto(resultados: list[Resultado]) -> tuple[str, str]:
    """Clasifica el producto (RNF9) y devuelve (estado, diagnóstico resumido)."""
    cadena = [r for r in resultados if r.capa in CAPAS]
    secundarias = [r for r in resultados if r.capa in SECUNDARIAS]
    error_diagnostico = next((r for r in secundarias if r.capa == "diagnostico" and r.estado == FAIL), None)
    if error_diagnostico:
        return "desconocido", f"no se pudo completar la evaluación: {error_diagnostico.detalle}"
    if any(r.datos.get("no_configurado") for r in cadena):
        falta = next(r.detalle for r in cadena if r.datos.get("no_configurado"))
        return "no configurado", falta
    ejecutadas = [r for r in cadena if r.estado != SKIP]
    if not ejecutadas:
        return "no probado", "todas las pruebas de la cadena quedaron en SKIP"
    falla = next((r for r in cadena if r.estado == FAIL), None)
    if falla:
        return "no disponible", f"falla en {falla.capa}: {falla.detalle} -> {falla.siguiente_paso}"
    if not any(r.capa == "lectura" and r.estado in (OK, WARN) for r in cadena):
        ultima = max((CAPAS.index(r.capa) for r in ejecutadas), default=0)
        return "desconocido", f"solo se probó hasta la capa '{CAPAS[ultima]}': no alcanza para declararlo disponible"
    degradan = [r for r in secundarias if r.estado == FAIL] + [
        r for r in resultados if r.datos.get("degrada")
    ]
    if degradan:
        r = degradan[0]
        return "degradado", f"{r.capa} / {r.prueba}: {r.detalle}"
    observaciones = [r for r in resultados if r.estado == WARN]
    if observaciones:
        return "disponible", f"observación: {observaciones[0].prueba}: {observaciones[0].detalle}"
    return "disponible", "todas las capas ejecutadas terminaron OK"


def matriz(registro: Registro, productos: list[str]) -> list[dict[str, Any]]:
    filas = []
    for producto in productos:
        propios = [r for r in registro.resultados if r.producto == producto]
        api = [r for r in registro.resultados if r.capa == "api" and producto in r.datos.get("dependencias", [])]
        estado, diagnostico = estado_producto(propios + [r for r in api if r not in propios])
        capas = {}
        for capa in CAPAS:
            estados = [r.estado for r in propios if r.capa == capa]
            capas[capa] = FAIL if FAIL in estados else (WARN if WARN in estados else (estados[0] if estados else "-"))
        lectura = [r.duracion_ms for r in propios if r.capa == "lectura" and r.estado in (OK, WARN) and r.duracion_ms]
        api_estado = "-" if not api else (FAIL if any(r.estado == FAIL for r in api) else (
            WARN if any(r.estado == WARN for r in api) else (SKIP if all(r.estado == SKIP for r in api) else OK)))
        sondas = [r for r in propios if r.capa == "sonda" and r.estado != SKIP]
        filas.append(
            {
                "producto": producto,
                "estado": estado,
                "capas": capas,
                "sondas": f"{sum(r.estado == OK for r in sondas)}/{len(sondas)}" if sondas else "-",
                "api": api_estado,
                "latencia_lectura_ms": round(max(lectura), 1) if lectura else None,
                "diagnostico": diagnostico,
            }
        )
    return filas

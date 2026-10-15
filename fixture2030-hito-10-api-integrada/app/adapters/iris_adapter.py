"""Adaptador de objetos: InterSystems IRIS (Hito 9, namespace configurado).

Usa la Native API de Python para invocar la fachada `Fixture.API`
(`iris/Fixture.API.cls`). Las operaciones se resuelven del lado de IRIS con el
modelo de objetos: apertura por el índice único `Codigo`, navegación de la
referencia `Arbitro` y de la relación `Eventos`, y `%Save()` con las
validaciones del Hito 9 (VALUELIST, MINVAL/MAXVAL y `%OnBeforeSave`).

El adaptador convierte el resultado JSON de la fachada en datos o en errores
de la aplicación; el %ID interno y los mensajes de %Status no salen de acá.

El cliente de IRIS no expone un timeout por operación, así que cada llamada se
ejecuta en un hilo con límite de espera (RNF8): si se supera, la request
responde 504 y la conexión se descarta.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTimeout
from typing import Any

import iris

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI
from app.core.observabilidad import logger

DEPENDENCIA = "iris"
CLASE_FACHADA = "Fixture.API"

_log = logger("adaptador.iris")


class _TimeoutIris(Exception):
    pass


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, _TimeoutIris):
        return timeout(DEPENDENCIA)
    # El cliente nativo informa caídas, credenciales y permisos como RuntimeError
    # (<COMMUNICATION LINK ERROR>, <PROTECT>, Access Denied).
    if isinstance(exc, (RuntimeError, OSError, ConnectionError)):
        return no_disponible(DEPENDENCIA)
    return None


class IrisAdapter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._conexion: Any = None
        self._nativo: Any = None
        # La conexión nativa no es thread-safe: una llamada a la vez.
        self._lock = threading.Lock()
        self._ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="iris")

    def _conectar(self) -> Any:
        if self._nativo is None:
            s = self._settings
            self._conexion = iris.connect(
                s.iris_host,
                s.iris_port,
                s.iris_namespace,
                s.iris_user,
                s.iris_password.get_secret_value(),
                timeout=int(s.timeout_conexion_s * 1000),
            )
            self._nativo = iris.createIRIS(self._conexion)
        return self._nativo

    def _descartar_conexion(self) -> None:
        try:
            if self._conexion is not None:
                self._conexion.close()
        except Exception:  # noqa: BLE001 - la conexión ya puede estar rota
            pass
        self._conexion = None
        self._nativo = None

    def _llamar(self, nombre: str, clase: str, metodo: str, *args: Any) -> str:
        """Invoca un método de clase con límite de espera y traducción de errores."""

        def llamada() -> str:
            with self._lock:
                try:
                    return self._conectar().classMethodValue(clase, metodo, *args)
                except Exception:
                    self._descartar_conexion()
                    raise

        limite = self._settings.timeout_conexion_s + self._settings.timeout_operacion_s
        with operacion(DEPENDENCIA, nombre, _traducir):
            futuro = self._ejecutor.submit(llamada)
            try:
                return futuro.result(timeout=limite)
            except FuturoTimeout as exc:
                raise _TimeoutIris() from exc

    def _invocar(self, metodo: str, *args: Any) -> dict[str, Any]:
        crudo = self._llamar(f"{CLASE_FACHADA}.{metodo}", CLASE_FACHADA, metodo, *args)
        resultado = json.loads(crudo)
        detalle = resultado.pop("detalle_interno", None)
        if detalle:
            _log.info("iris_detalle metodo=%s error=%s detalle=%s", metodo, resultado.get("error"), detalle)
        return resultado

    def obtener_acta(self, codigo: str) -> dict[str, Any]:
        return self._invocar("ObtenerActa", codigo)

    def cambiar_estado(self, codigo: str, estado: str) -> dict[str, Any]:
        return self._invocar("CambiarEstado", codigo, estado)

    def registrar_evento(self, codigo: str, minuto: int, tipo: str, descripcion: str) -> dict[str, Any]:
        return self._invocar("RegistrarEvento", codigo, minuto, tipo, descripcion)

    def ping(self) -> None:
        self._llamar("ping", "%SYSTEM.Version", "GetNumber")

    def cerrar(self) -> None:
        with self._lock:
            self._descartar_conexion()
        self._ejecutor.shutdown(wait=False, cancel_futures=True)

"""IRIS por DB-API: SELECT parametrizados sobre la proyección del Hito 9.

Sin fachada ObjectScript ni operaciones de escritura. Un límite externo acota
la espera del cliente; las llamadas a la conexión se serializan.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoTimeout
from typing import Any
import iris.dbapi
from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI

DEPENDENCIA = "iris"
SQL_ACTA = """
SELECT Codigo, Sede, Fecha, Estado,
       Arbitro->Nombre, Arbitro->Apellido, Arbitro->Rango
FROM Fixture.Partido WHERE Codigo = ?
"""
SQL_EVENTOS = """
SELECT TOP 200 e.Minuto, e.Tipo, e.Descripcion
FROM Fixture.Evento e JOIN Fixture.Partido p ON e.Partido = p.ID
WHERE p.Codigo = ? ORDER BY e.Minuto
"""

class _TimeoutIris(Exception):
    pass

def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, _TimeoutIris):
        return timeout(DEPENDENCIA)
    if isinstance(exc, (iris.dbapi.Error, RuntimeError, OSError)):
        return no_disponible(DEPENDENCIA)
    return None

class IrisAdapter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._conexion = None
        self._lock = threading.Lock()
        self._ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="iris-lectura")

    def _conectar(self):
        if self._conexion is None:
            s = self._settings
            self._conexion = iris.dbapi.connect(s.iris_host, s.iris_port, s.iris_namespace,
                s.iris_user, s.iris_password.get_secret_value(), timeout=int(s.timeout_conexion_s * 1000))
        return self._conexion

    def _consultar(self, sql, parametros):
        cursor = self._conectar().cursor()
        try:
            cursor.execute(sql, parametros)
            return cursor.fetchall()
        finally:
            cursor.close()

    def _ejecutar(self, nombre, llamada):
        def protegida():
            with self._lock:
                return llamada()
        with operacion(DEPENDENCIA, nombre, _traducir):
            futuro = self._ejecutor.submit(protegida)
            try:
                return futuro.result(timeout=self._settings.timeout_conexion_s + self._settings.timeout_operacion_s)
            except FuturoTimeout as exc:
                futuro.cancel()
                raise _TimeoutIris() from exc

    def obtener_acta(self, codigo: str) -> dict[str, Any] | None:
        def leer():
            filas = self._consultar(SQL_ACTA, [codigo])
            if not filas:
                return None
            f = filas[0]
            eventos = self._consultar(SQL_EVENTOS, [codigo])
            return {"codigo_partido": f[0], "sede": f[1], "fecha": f[2], "estado": f[3],
                    "arbitro": {"nombre": f[4], "apellido": f[5], "rango": f[6]},
                    "eventos": [{"minuto": e[0], "tipo": e[1], "descripcion": e[2]} for e in eventos]}
        return self._ejecutar("acta.select", leer)

    def ping(self):
        self._ejecutar("ping", lambda: self._consultar("SELECT 1", []))

    def cerrar(self):
        self._ejecutor.shutdown(wait=False, cancel_futures=True)
        if self._lock.acquire(blocking=False):
            try:
                if self._conexion is not None:
                    self._conexion.close()
            finally:
                self._lock.release()

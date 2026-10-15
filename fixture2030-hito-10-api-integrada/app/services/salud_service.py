"""Caso de uso CU16: disponibilidad de las seis fuentes, chequeadas en paralelo."""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.core.errores import DependenciaTimeout, ErrorAPI
from app.core.observabilidad import logger, request_id_actual
from app.schemas.salud import Dependencia, EstadoDependencia, Salud

_log = logger("servicio.salud")


class SaludService:
    def __init__(self, adaptadores: dict[str, Any]):
        self._adaptadores = adaptadores

    def _chequear(self, nombre: str, adaptador: Any, request_id: str) -> Dependencia:
        token = request_id_actual.set(request_id)  # los hilos no heredan la ContextVar
        inicio = time.perf_counter()
        try:
            adaptador.ping()
            estado = EstadoDependencia.ok
        except DependenciaTimeout:
            estado = EstadoDependencia.timeout
        except ErrorAPI:
            estado = EstadoDependencia.caida
        except Exception:  # noqa: BLE001 - un chequeo nunca debe tumbar /health
            _log.exception("dependencia=%s resultado=error_inesperado", nombre)
            estado = EstadoDependencia.caida
        finally:
            request_id_actual.reset(token)
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        return Dependencia(nombre=nombre, estado=estado, latencia_ms=latencia)

    def verificar(self) -> Salud:
        request_id = request_id_actual.get()
        with ThreadPoolExecutor(max_workers=len(self._adaptadores)) as ejecutor:
            futuros = [
                ejecutor.submit(self._chequear, nombre, adaptador, request_id)
                for nombre, adaptador in self._adaptadores.items()
            ]
            dependencias = [f.result() for f in futuros]
        todas_ok = all(d.estado == EstadoDependencia.ok for d in dependencias)
        return Salud(estado="ok" if todas_ok else "degradado", dependencias=dependencias)

"""Comportamiento común de los adaptadores (sección 5.2).

`operacion()` envuelve cada llamada a un driver para:
  * medir la duración y registrar dependencia, operación y resultado (RNF10);
  * traducir las excepciones propias del driver a errores de la aplicación
    (DependenciaNoDisponible / DependenciaTimeout), sin dejar pasar mensajes
    del driver al consumidor (RF12, RNF9).

Cada adaptador provee su función `traducir`, porque solo él conoce las
excepciones de su cliente nativo (RNF5).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.errores import DependenciaNoDisponible, DependenciaTimeout, ErrorAPI
from app.core.observabilidad import logger

_log = logger("adaptador")

# Devuelve el ErrorAPI equivalente, o None si la excepción no es de disponibilidad
# (en ese caso se propaga y termina como 500 con el detalle solo en el log).
Traductor = Callable[[Exception], ErrorAPI | None]


@contextmanager
def operacion(dependencia: str, nombre: str, traducir: Traductor) -> Iterator[None]:
    inicio = time.perf_counter()
    try:
        yield
    except ErrorAPI as error:
        _registrar(dependencia, nombre, inicio, error.codigo)
        raise
    except Exception as exc:  # noqa: BLE001 - se traduce o se propaga
        error = traducir(exc)
        if error is None:
            _registrar(dependencia, nombre, inicio, f"error_inesperado:{type(exc).__name__}")
            raise
        _registrar(dependencia, nombre, inicio, f"{error.codigo}:{type(exc).__name__}")
        raise error from exc
    else:
        _registrar(dependencia, nombre, inicio, "ok")


def _registrar(dependencia: str, nombre: str, inicio: float, resultado: str) -> None:
    duracion_ms = (time.perf_counter() - inicio) * 1000
    nivel = 20 if resultado == "ok" else 30  # INFO / WARNING
    _log.log(
        nivel,
        "dependencia=%s operacion=%s resultado=%s duracion_ms=%.1f",
        dependencia,
        nombre,
        resultado,
        duracion_ms,
    )


def no_disponible(dependencia: str) -> DependenciaNoDisponible:
    return DependenciaNoDisponible(dependencia)


def timeout(dependencia: str) -> DependenciaTimeout:
    return DependenciaTimeout(dependencia)

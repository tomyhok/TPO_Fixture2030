"""Salud de la API y de sus fuentes.

* CU16 `verificar()` (Hito 10, `/health`): ping a las seis fuentes en cada llamada.
* Hito 11:
  - `vida()` (`/health/live`): no consulta ninguna base.
  - `diagnostico()` (`/health/dependencias`): chequeo profundo por fuente con
    estados up/down/degraded/unknown/not_configured. El resultado se reutiliza
    durante `ttl_cache_s` para que ni un balanceador ni un usuario insistente
    consulten las seis bases en cada request (sección 5.6).
  - `preparacion()` (`/health/ready`): decisión de readiness sobre ese diagnóstico.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from app.core.errores import DependenciaTimeout, ErrorAPI
from app.core.observabilidad import logger, request_id_actual
from app.schemas.salud import (
    Dependencia,
    Diagnostico,
    DiagnosticoDependencia,
    EstadoComponente,
    EstadoDependencia,
    Preparacion,
    Salud,
    Vida,
)

_log = logger("servicio.salud")

DISPONIBLES = (EstadoComponente.up, EstadoComponente.degraded)


class SaludService:
    def __init__(
        self,
        adaptadores: dict[str, Any],
        faltantes: dict[str, list[str]] | None = None,
        ttl_cache_s: float = 10.0,
        umbral_lento_ms: float = 1000.0,
        version: str = "",
    ):
        self._adaptadores = adaptadores
        self._faltantes = faltantes or {}
        self._ttl_cache_s = ttl_cache_s
        self._umbral_lento_ms = umbral_lento_ms
        self._version = version
        self._inicio = time.monotonic()
        # Un solo chequeo profundo a la vez: las llamadas concurrentes esperan y
        # reciben el mismo resultado en lugar de multiplicar las consultas.
        self._lock = threading.Lock()
        self._cache: Diagnostico | None = None
        self._cache_monotonic = 0.0

    # ------------------------------------------------------- Hito 10 /health
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

    # ------------------------------------------------------ Hito 11 liveness
    def vida(self) -> Vida:
        return Vida(estado="up", version=self._version, activa_desde_s=round(time.monotonic() - self._inicio, 1))

    # ---------------------------------------------- Hito 11 diagnóstico profundo
    def _diagnosticar(self, nombre: str, adaptador: Any, request_id: str) -> DiagnosticoDependencia:
        faltantes = self._faltantes.get(nombre) or []
        if faltantes:
            return DiagnosticoDependencia(
                nombre=nombre,
                estado=EstadoComponente.not_configured,
                motivo="FALTA_CONFIGURACION:" + ",".join(faltantes),
            )
        token = request_id_actual.set(request_id)
        inicio = time.perf_counter()
        motivo: str | None = None
        try:
            adaptador.ping()
            estado = EstadoComponente.up
        except ErrorAPI as error:  # DependenciaNoDisponible / DependenciaTimeout
            estado, motivo = EstadoComponente.down, error.codigo
        except Exception:  # noqa: BLE001 - no se pudo evaluar: no es "caída" ni "ok"
            _log.exception("dependencia=%s resultado=error_inesperado", nombre)
            estado, motivo = EstadoComponente.unknown, "ERROR_INESPERADO"
        finally:
            request_id_actual.reset(token)
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        if estado == EstadoComponente.up and latencia > self._umbral_lento_ms:
            estado, motivo = EstadoComponente.degraded, "LATENCIA_ALTA"
        return DiagnosticoDependencia(nombre=nombre, estado=estado, motivo=motivo, latencia_ms=latencia)

    def _evaluar(self) -> Diagnostico:
        request_id = request_id_actual.get()
        with ThreadPoolExecutor(max_workers=len(self._adaptadores)) as ejecutor:
            futuros = [
                ejecutor.submit(self._diagnosticar, nombre, adaptador, request_id)
                for nombre, adaptador in self._adaptadores.items()
            ]
            dependencias = [f.result() for f in futuros]
        estados = [d.estado for d in dependencias]
        if all(e == EstadoComponente.up for e in estados):
            general = EstadoComponente.up
        elif any(e in DISPONIBLES for e in estados):
            general = EstadoComponente.degraded
        else:
            general = EstadoComponente.down
        _log.info(
            "diagnostico estado=%s %s",
            general,
            " ".join(f"{d.nombre}={d.estado}" for d in dependencias),
        )
        return Diagnostico(
            estado=general,
            verificado_en=datetime.now(UTC),
            desde_cache=False,
            edad_s=0.0,
            ttl_cache_s=self._ttl_cache_s,
            dependencias=dependencias,
        )

    def diagnostico(self, refrescar: bool = False) -> Diagnostico:
        with self._lock:
            edad = time.monotonic() - self._cache_monotonic
            if self._cache is not None and not refrescar and edad < self._ttl_cache_s:
                return self._cache.model_copy(update={"desde_cache": True, "edad_s": round(edad, 1)})
            self._cache = self._evaluar()
            self._cache_monotonic = time.monotonic()
            return self._cache

    # ----------------------------------------------------- Hito 11 readiness
    def preparacion(self) -> Preparacion:
        """La API está lista si al menos una fuente está disponible.

        Cada ruta depende de una fuente propia: sacar la API de servicio porque
        cae una sola fuente cortaría también los módulos sanos. Las rutas de la
        fuente caída responden 503/504 con la dependencia identificada.
        """
        diag = self.diagnostico()
        disponibles = [d.nombre for d in diag.dependencias if d.estado in DISPONIBLES]
        return Preparacion(
            listo=bool(disponibles),
            estado=diag.estado,
            disponibles=disponibles,
            no_disponibles=[d.nombre for d in diag.dependencias if d.estado not in DISPONIBLES],
            verificado_en=diag.verificado_en,
            desde_cache=diag.desde_cache,
        )

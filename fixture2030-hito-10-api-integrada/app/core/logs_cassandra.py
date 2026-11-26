"""Persistencia asíncrona y resiliente de logs operativos en Apache Cassandra.

Arquitectura productor-consumidor desacoplada:
  * El hilo HTTP (productor) convierte cada LogRecord en un EventoLog y lo encola
    con `put_nowait` en una cola acotada en memoria (sin bloquear jamás la request).
  * Un hilo en segundo plano (consumidor) drena micro-lotes cada `flush_interval_s`
    o al alcanzar `batch_size`, y los persiste en Cassandra.
  * Ante cola llena o caída de Cassandra se descartan eventos de telemetría
    contabilizando el motivo en Prometheus (`fixture_api_logs_dropped_total`)
    sin propagar errores ni generar recursión sobre el logger `fixture2030.*`.
"""

import logging
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.metricas import metricas
from app.core.observabilidad import request_id_actual

NIVELES_INCIDENTE: frozenset[str] = frozenset({"WARNING", "ERROR", "CRITICAL"})
_AVISO_STDERR_INTERVALO_S = 30.0
_BACKOFF_INICIAL_S = 1.0
_BACKOFF_MAXIMO_S = 30.0
_MAX_LARGO_MENSAJE = 2000


@dataclass(frozen=True)
class EventoLog:
    creado_en: datetime
    ventana_hora: str
    fecha: str
    servicio: str
    nivel: str
    logger: str
    request_id: str
    metodo: str | None
    ruta: str | None
    status_http: int | None
    dependencia: str | None
    operacion: str | None
    resultado: str | None
    duracion_ms: float | None
    mensaje: str
    instancia: str


class PersistorLogsCassandra:
    """Cola acotada y worker en segundo plano para persistir lotes de logs en Cassandra."""

    def __init__(
        self,
        escritor: Any,
        servicio: str = "fixture2030-api",
        queue_size: int = 2000,
        batch_size: int = 50,
        flush_interval_s: float = 1.0,
        ttl_s: int = 2592000,
        backoff_inicial_s: float = _BACKOFF_INICIAL_S,
        backoff_maximo_s: float = _BACKOFF_MAXIMO_S,
    ) -> None:
        self._escritor = escritor
        self._servicio = servicio
        self._batch_size = max(1, batch_size)
        self._flush_interval_s = max(0.05, flush_interval_s)
        self._ttl_s = max(0, ttl_s)
        self._cola: queue.Queue[EventoLog] = queue.Queue(maxsize=max(1, queue_size))
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._lock_aviso = threading.Lock()
        self._ultimo_aviso_stderr = 0.0
        # Espera antes de reintentar tras un error de Cassandra (exponencial, con tope).
        # Evita que el worker reintente conectar en cada lote y retenga el lock de
        # sesión del adaptador, que también usan las lecturas HTTP de comentarios.
        self._backoff_inicial_s = max(0.0, backoff_inicial_s)
        self._backoff_maximo_s = max(self._backoff_inicial_s, backoff_maximo_s)
        self._backoff_s = 0.0
        metricas.actualizar_cola_logs(0)

    def iniciar(self) -> None:
        if self._hilo is not None and self._hilo.is_alive():
            return
        self._detener.clear()
        self._hilo = threading.Thread(
            target=self._bucle,
            name="cassandra-log-writer",
            daemon=True,
        )
        self._hilo.start()

    def encolar(self, evento: EventoLog) -> bool:
        if self._detener.is_set():
            metricas.registrar_logs_descartados("shutdown_timeout")
            return False
        try:
            self._cola.put_nowait(evento)
        except queue.Full:
            metricas.registrar_logs_descartados("queue_full")
            return False
        metricas.actualizar_cola_logs(self._cola.qsize())
        return True

    def _bucle(self) -> None:
        while True:
            if self._detener.is_set() and self._cola.empty():
                break
            try:
                primero = self._cola.get(timeout=self._flush_interval_s)
            except queue.Empty:
                if self._detener.is_set():
                    break
                continue

            lote = [primero]
            while len(lote) < self._batch_size:
                try:
                    lote.append(self._cola.get_nowait())
                except queue.Empty:
                    break

            self._vaciar_lote(lote)
            metricas.actualizar_cola_logs(self._cola.qsize())

    def _vaciar_lote(self, lote: list[EventoLog]) -> None:
        try:
            persistidos = int(self._escritor.escribir_lote_logs(lote, self._ttl_s))
        except Exception as exc:  # noqa: BLE001 - telemetría nunca puede romper ni recursar
            metricas.registrar_logs_descartados("cassandra_error", len(lote))
            self._avisar_stderr(type(exc).__name__, len(lote))
            self._esperar_backoff()
            return

        persistidos = max(0, min(persistidos, len(lote)))
        metricas.registrar_logs_persistidos(persistidos)
        fallidos = len(lote) - persistidos
        if fallidos > 0:
            # Cassandra respondió pero algunos INSERT fallaron: se descartan solo esos.
            metricas.registrar_logs_descartados("cassandra_error", fallidos)
            self._avisar_stderr("escritura_parcial", fallidos)
        self._backoff_s = 0.0

    def _esperar_backoff(self) -> None:
        if self._backoff_s <= 0:
            self._backoff_s = self._backoff_inicial_s
        else:
            self._backoff_s = min(self._backoff_s * 2, self._backoff_maximo_s)
        # wait() en vez de sleep(): cerrar() interrumpe la espera de inmediato.
        self._detener.wait(self._backoff_s)

    def _avisar_stderr(self, causa: str, cantidad: int) -> None:
        ahora = time.monotonic()
        with self._lock_aviso:
            if ahora - self._ultimo_aviso_stderr < _AVISO_STDERR_INTERVALO_S:
                return
            self._ultimo_aviso_stderr = ahora
        try:
            sys.stderr.write(
                f"[logs_cassandra] error persistiendo {cantidad} logs en Cassandra: "
                f"{causa}\n"
            )
            sys.stderr.flush()
        except OSError:
            pass

    def cerrar(self, timeout_s: float = 2.0) -> None:
        self._detener.set()
        if self._hilo is not None and self._hilo.is_alive():
            self._hilo.join(timeout=max(0.1, timeout_s))

        restantes = 0
        while True:
            try:
                self._cola.get_nowait()
                restantes += 1
            except queue.Empty:
                break
        if restantes > 0:
            metricas.registrar_logs_descartados("shutdown_timeout", restantes)
        metricas.actualizar_cola_logs(0)


class CassandraLogHandler(logging.Handler):
    """Handler de Python `logging` que envía eventos estructurados al persistor asíncrono."""

    def __init__(
        self,
        persistor: PersistorLogsCassandra,
        servicio: str = "fixture2030-api",
        instancia: str | None = None,
    ) -> None:
        super().__init__()
        self._persistor = persistor
        self._servicio = servicio
        self._instancia = instancia or socket.gethostname()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            creado_en = datetime.fromtimestamp(record.created, tz=UTC)
            request_id = getattr(record, "request_id", None) or request_id_actual.get() or "-"
            ctx = getattr(record, "log_ctx", None)
            ctx_dict = ctx if isinstance(ctx, dict) else {}

            mensaje = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                mensaje = f"{mensaje} exc={type(record.exc_info[1]).__name__}"
            if len(mensaje) > _MAX_LARGO_MENSAJE:
                mensaje = mensaje[:_MAX_LARGO_MENSAJE]

            duracion_raw = ctx_dict.get("duracion_ms")
            status_raw = ctx_dict.get("status_http")

            evento = EventoLog(
                creado_en=creado_en,
                ventana_hora=creado_en.strftime("%Y%m%d%H"),
                fecha=creado_en.strftime("%Y%m%d"),
                servicio=self._servicio,
                nivel=record.levelname.upper(),
                logger=record.name,
                request_id=str(request_id),
                metodo=ctx_dict.get("metodo"),
                ruta=ctx_dict.get("ruta"),
                status_http=int(status_raw) if status_raw is not None else None,
                dependencia=ctx_dict.get("dependencia"),
                operacion=ctx_dict.get("operacion"),
                resultado=ctx_dict.get("resultado"),
                duracion_ms=float(duracion_raw) if duracion_raw is not None else None,
                mensaje=mensaje,
                instancia=self._instancia,
            )
            self._persistor.encolar(evento)
        except Exception:  # noqa: BLE001 - un fallo de logging jamás debe escalar
            pass

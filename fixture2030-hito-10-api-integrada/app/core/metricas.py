"""Métricas Prometheus de la API integrada y de los seis motores NoSQL (Hito 13).

Expone en formato de texto Prometheus (0.0.4) los tipos de métricas vistos en la
Clase 14 (Counter, Gauge, Histogram), diferenciando:
  * métricas de aplicación HTTP (tráfico, latencia, requests en curso y errores);
  * métricas por base de datos / subsistema obtenidas de los adaptadores y del
    diagnóstico de salud (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`).
"""

import threading
import time
from typing import Any

BUCKETS_HTTP_S: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
BUCKETS_DB_S: tuple[float, ...] = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

MOTORES: tuple[str, ...] = ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris")
ESTADOS_MOTOR: tuple[str, ...] = ("up", "degraded", "down", "not_configured", "unknown")
ESTADOS_DISPONIBLES: frozenset[str] = frozenset({"up", "degraded"})


def _escapar(valor: str) -> str:
    return str(valor).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _formatear_labels(etiquetas: dict[str, Any]) -> str:
    if not etiquetas:
        return ""
    partes = [f'{k}="{_escapar(str(v))}"' for k, v in etiquetas.items()]
    return "{" + ",".join(partes) + "}"


def _estado_str(estado: Any) -> str:
    return str(getattr(estado, "value", estado))


class RegistroMetricas:
    """Registro thread-safe de métricas en memoria con serialización Prometheus 0.0.4."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inicio = time.monotonic()
        self.reiniciar()

    def reiniciar(self) -> None:
        with self._lock:
            self._inicio = time.monotonic()
            self._in_flight = 0
            self._http_requests: dict[tuple[str, str, str], int] = {}
            self._http_errors: dict[tuple[str, str, str], int] = {}
            self._http_hist_buckets: dict[tuple[str, str], list[int]] = {}
            self._http_hist_sum: dict[tuple[str, str], float] = {}
            self._http_hist_count: dict[tuple[str, str], int] = {}

            self._db_ops: dict[tuple[str, str, str], int] = {}
            self._db_hist_buckets: dict[tuple[str, str], list[int]] = {}
            self._db_hist_sum: dict[tuple[str, str], float] = {}
            self._db_hist_count: dict[tuple[str, str], int] = {}

    # ------------------------------------------------------- Instrumentación HTTP
    def iniciar_request(self) -> None:
        with self._lock:
            self._in_flight += 1

    def finalizar_request(self, metodo: str, ruta: str, status_code: int, duracion_s: float) -> None:
        clave_req = (metodo, ruta, str(status_code))
        clave_hist = (metodo, ruta)
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._http_requests[clave_req] = self._http_requests.get(clave_req, 0) + 1
            if clave_hist not in self._http_hist_buckets:
                self._http_hist_buckets[clave_hist] = [0] * len(BUCKETS_HTTP_S)
                self._http_hist_sum[clave_hist] = 0.0
                self._http_hist_count[clave_hist] = 0
            conteos = self._http_hist_buckets[clave_hist]
            for idx, limite in enumerate(BUCKETS_HTTP_S):
                if duracion_s <= limite:
                    conteos[idx] += 1
            self._http_hist_sum[clave_hist] += max(0.0, duracion_s)
            self._http_hist_count[clave_hist] += 1

    def registrar_error_http(self, metodo: str, ruta: str, codigo: str) -> None:
        clave = (metodo, ruta, codigo)
        with self._lock:
            self._http_errors[clave] = self._http_errors.get(clave, 0) + 1

    # ------------------------------------------------ Instrumentación Adaptadores
    def registrar_operacion_db(
        self, dependencia: str, operacion: str, resultado: str, duracion_s: float
    ) -> None:
        estado = "ok" if resultado == "ok" else resultado.split(":", 1)[0]
        clave_op = (dependencia, operacion, estado)
        clave_hist = (dependencia, operacion)
        with self._lock:
            self._db_ops[clave_op] = self._db_ops.get(clave_op, 0) + 1
            if clave_hist not in self._db_hist_buckets:
                self._db_hist_buckets[clave_hist] = [0] * len(BUCKETS_DB_S)
                self._db_hist_sum[clave_hist] = 0.0
                self._db_hist_count[clave_hist] = 0
            conteos = self._db_hist_buckets[clave_hist]
            for idx, limite in enumerate(BUCKETS_DB_S):
                if duracion_s <= limite:
                    conteos[idx] += 1
            self._db_hist_sum[clave_hist] += max(0.0, duracion_s)
            self._db_hist_count[clave_hist] += 1

    # ------------------------------------------------- Exportación Prometheus 0.0.4
    def exportar_prometheus(self, diagnostico: Any = None) -> str:
        with self._lock:
            uptime_s = max(0.0, time.monotonic() - self._inicio)
            in_flight = self._in_flight
            http_requests = dict(self._http_requests)
            http_errors = dict(self._http_errors)
            http_hist_buckets = {k: list(v) for k, v in self._http_hist_buckets.items()}
            http_hist_sum = dict(self._http_hist_sum)
            http_hist_count = dict(self._http_hist_count)
            db_ops = dict(self._db_ops)
            db_hist_buckets = {k: list(v) for k, v in self._db_hist_buckets.items()}
            db_hist_sum = dict(self._db_hist_sum)
            db_hist_count = dict(self._db_hist_count)

        lineas: list[str] = []

        # 1. Salud y estado de la API
        lineas.extend(
            [
                "# HELP fixture_api_up Disponibilidad del proceso de la API integrada (1 = UP).",
                "# TYPE fixture_api_up gauge",
                "fixture_api_up 1",
                "# HELP fixture_api_uptime_seconds Tiempo transcurrido desde el inicio del proceso de la API.",
                "# TYPE fixture_api_uptime_seconds gauge",
                f"fixture_api_uptime_seconds {uptime_s:.3f}",
                "# HELP fixture_api_in_flight_requests Cantidad de solicitudes HTTP actualmente en curso.",
                "# TYPE fixture_api_in_flight_requests gauge",
                f"fixture_api_in_flight_requests {in_flight}",
            ]
        )

        # 2. Disponibilidad y latencia de ping por base de datos NoSQL
        lineas.extend(
            [
                "# HELP fixture_db_up Disponibilidad de cada base de datos NoSQL (1 = up/degraded, 0 = down/not_configured/unknown).",
                "# TYPE fixture_db_up gauge",
            ]
        )
        dependencias = getattr(diagnostico, "dependencias", None) or []
        por_motor = {d.nombre: d for d in dependencias}
        for motor in MOTORES:
            dep = por_motor.get(motor)
            estado_actual = _estado_str(dep.estado) if dep is not None else "unknown"
            disponible = 1 if estado_actual in ESTADOS_DISPONIBLES else 0
            lineas.append(f'fixture_db_up{{db="{motor}"}} {disponible}')

        lineas.extend(
            [
                "# HELP fixture_db_status_info Estado detallado de cada base de datos según el diagnóstico de salud.",
                "# TYPE fixture_db_status_info gauge",
            ]
        )
        for motor in MOTORES:
            dep = por_motor.get(motor)
            estado_actual = _estado_str(dep.estado) if dep is not None else "unknown"
            for est in ESTADOS_MOTOR:
                valor = 1 if estado_actual == est else 0
                lineas.append(f'fixture_db_status_info{{db="{motor}",state="{est}"}} {valor}')

        lineas.extend(
            [
                "# HELP fixture_db_ping_latency_seconds Latencia del chequeo de salud (ping) hacia cada base de datos en segundos.",
                "# TYPE fixture_db_ping_latency_seconds gauge",
            ]
        )
        for motor in MOTORES:
            dep = por_motor.get(motor)
            lat_ms = getattr(dep, "latencia_ms", None) if dep is not None else None
            latencia_s = (float(lat_ms) / 1000.0) if lat_ms is not None else 0.0
            lineas.append(f'fixture_db_ping_latency_seconds{{db="{motor}"}} {latencia_s:.6f}')

        # 3. Contadores HTTP de la API
        lineas.extend(
            [
                "# HELP fixture_api_http_requests_total Total de solicitudes HTTP procesadas por la API.",
                "# TYPE fixture_api_http_requests_total counter",
            ]
        )
        for (metodo, ruta, status), total in sorted(http_requests.items()):
            etiquetas = _formatear_labels({"method": metodo, "route": ruta, "status": status})
            lineas.append(f"fixture_api_http_requests_total{etiquetas} {total}")

        lineas.extend(
            [
                "# HELP fixture_api_http_errors_total Total de respuestas de error devueltas por la API según código de error.",
                "# TYPE fixture_api_http_errors_total counter",
            ]
        )
        for (metodo, ruta, codigo), total in sorted(http_errors.items()):
            etiquetas = _formatear_labels({"method": metodo, "route": ruta, "codigo": codigo})
            lineas.append(f"fixture_api_http_errors_total{etiquetas} {total}")

        # 4. Histograma de latencia HTTP de la API
        lineas.extend(
            [
                "# HELP fixture_api_http_request_duration_seconds Duración de las solicitudes HTTP en segundos.",
                "# TYPE fixture_api_http_request_duration_seconds histogram",
            ]
        )
        for (metodo, ruta), conteos in sorted(http_hist_buckets.items()):
            total_count = http_hist_count[(metodo, ruta)]
            total_sum = http_hist_sum[(metodo, ruta)]
            for idx, limite in enumerate(BUCKETS_HTTP_S):
                etiquetas = _formatear_labels({"method": metodo, "route": ruta, "le": f"{limite:g}"})
                lineas.append(f"fixture_api_http_request_duration_seconds_bucket{etiquetas} {conteos[idx]}")
            etiquetas_inf = _formatear_labels({"method": metodo, "route": ruta, "le": "+Inf"})
            lineas.append(f"fixture_api_http_request_duration_seconds_bucket{etiquetas_inf} {total_count}")
            etiquetas_base = _formatear_labels({"method": metodo, "route": ruta})
            lineas.append(f"fixture_api_http_request_duration_seconds_sum{etiquetas_base} {total_sum:.6f}")
            lineas.append(f"fixture_api_http_request_duration_seconds_count{etiquetas_base} {total_count}")

        # 5. Contadores e histograma de operaciones por base de datos NoSQL
        lineas.extend(
            [
                "# HELP fixture_db_operations_total Total de operaciones ejecutadas por los adaptadores hacia cada base de datos.",
                "# TYPE fixture_db_operations_total counter",
            ]
        )
        for (db, op, status), total in sorted(db_ops.items()):
            etiquetas = _formatear_labels({"db": db, "operation": op, "status": status})
            lineas.append(f"fixture_db_operations_total{etiquetas} {total}")

        lineas.extend(
            [
                "# HELP fixture_db_operation_duration_seconds Duración de las operaciones contra cada base de datos en segundos.",
                "# TYPE fixture_db_operation_duration_seconds histogram",
            ]
        )
        for (db, op), conteos in sorted(db_hist_buckets.items()):
            total_count = db_hist_count[(db, op)]
            total_sum = db_hist_sum[(db, op)]
            for idx, limite in enumerate(BUCKETS_DB_S):
                etiquetas = _formatear_labels({"db": db, "operation": op, "le": f"{limite:g}"})
                lineas.append(f"fixture_db_operation_duration_seconds_bucket{etiquetas} {conteos[idx]}")
            etiquetas_inf = _formatear_labels({"db": db, "operation": op, "le": "+Inf"})
            lineas.append(f"fixture_db_operation_duration_seconds_bucket{etiquetas_inf} {total_count}")
            etiquetas_base = _formatear_labels({"db": db, "operation": op})
            lineas.append(f"fixture_db_operation_duration_seconds_sum{etiquetas_base} {total_sum:.6f}")
            lineas.append(f"fixture_db_operation_duration_seconds_count{etiquetas_base} {total_count}")

        return "\n".join(lineas) + "\n"


metricas = RegistroMetricas()

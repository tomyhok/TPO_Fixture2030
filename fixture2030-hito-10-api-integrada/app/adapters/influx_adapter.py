"""Adaptador temporal: InfluxDB 3 Core (Hito 8, tabla `estadisticas_partido`).

Consulta por la API HTTP v3 (`/api/v3/query_sql`) con SQL parametrizado: los
valores del consumidor viajan en `params`, nunca concatenados. La única parte
variable del texto SQL es el intervalo de `date_bin`, que sale de una lista
cerrada (`INTERVALOS`) y no del consumidor.

Agregaciones correctas según la semántica de cada medida (Hito 8, sección 3):
AVG para la posesión (gauge), MAX para los contadores acumulados y para el
pico de usuarios.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import DependenciaNoDisponible, ErrorAPI

DEPENDENCIA = "influxdb"

INTERVALOS = {"10s": "10 seconds", "1m": "1 minute", "5m": "5 minutes"}

_SQL_SERIE = """
SELECT date_bin(INTERVAL '{intervalo}', time) AS instante,
       equipo_id,
       AVG(posesion_pct) AS posesion_pct_prom,
       MAX(pases_completados) AS pases_completados_max,
       MAX(tiros) AS tiros_max,
       MAX(usuarios_activos) AS usuarios_activos_max
FROM estadisticas_partido
WHERE partido_id = $partido
  {filtro_equipo}
  AND time >= $desde AND time < $hasta
GROUP BY 1, 2
ORDER BY equipo_id, instante
LIMIT $tope
"""


class _RespuestaInvalida(Exception):
    """La fuente respondió con un estado que no es de datos (auth, base inexistente)."""


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, httpx.TimeoutException):
        return timeout(DEPENDENCIA)
    if isinstance(exc, (httpx.TransportError, _RespuestaInvalida)):
        return no_disponible(DEPENDENCIA)
    return None


def _a_utc(valor: str) -> datetime:
    # InfluxDB devuelve "2030-06-10T20:00:00" sin zona: es UTC.
    return datetime.fromisoformat(valor).replace(tzinfo=UTC)


class InfluxAdapter:
    def __init__(self, settings: Settings):
        self._database = settings.influx_database
        self._token = settings.token_influx()
        self._cliente = httpx.Client(
            base_url=settings.influx_url,
            timeout=httpx.Timeout(settings.timeout_operacion_s, connect=settings.timeout_conexion_s),
        )

    def _consultar(self, nombre: str, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with operacion(DEPENDENCIA, nombre, _traducir):
            if not self._token:
                raise DependenciaNoDisponible(DEPENDENCIA)
            r = self._cliente.post(
                "/api/v3/query_sql",
                json={"db": self._database, "q": sql, "params": params, "format": "json"},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if r.status_code != 200:
                # 401 (token), 404 (database inexistente) o 5xx: es una falla de la
                # fuente, no "cero puntos". El cuerpo solo se registra truncado.
                raise _RespuestaInvalida(f"HTTP {r.status_code}: {r.text[:120]}")
            return r.json() if r.content else []

    def serie_partido(
        self,
        codigo_partido: str,
        equipo: str | None,
        desde: datetime,
        hasta: datetime,
        resolucion: str,
        tope: int,
    ) -> list[dict[str, Any]]:
        sql = _SQL_SERIE.format(
            intervalo=INTERVALOS[resolucion],
            filtro_equipo="AND equipo_id = $equipo" if equipo else "",
        )
        params: dict[str, Any] = {
            "partido": codigo_partido,
            "desde": desde.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hasta": hasta.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tope": tope,
        }
        if equipo:
            params["equipo"] = equipo
        filas = self._consultar("estadisticas_partido.date_bin", sql, params)
        for fila in filas:
            fila["instante"] = _a_utc(fila["instante"])
            fila["posesion_pct_prom"] = round(fila["posesion_pct_prom"], 2)
        return filas

    def ping(self) -> None:
        self._consultar("ping", "SELECT 1 AS ok", {})

    def cerrar(self) -> None:
        self._cliente.close()

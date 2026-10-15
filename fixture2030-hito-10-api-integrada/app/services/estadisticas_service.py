"""Caso de uso CU12 (estadísticas por ventana temporal en InfluxDB)."""

import math
from datetime import datetime, timedelta
from typing import Any

from app.core.errores import ErrorValidacion
from app.schemas.estadisticas import EstadisticasPartido, Resolucion, SerieEquipo

VENTANA_MAXIMA = timedelta(hours=3)
SEGUNDOS_RESOLUCION = {Resolucion.s10: 10, Resolucion.m1: 60, Resolucion.m5: 300}


def validar_intervalo(desde: datetime, hasta: datetime) -> None:
    detalles = []
    if desde.tzinfo is None:
        detalles.append({"campo": "query.desde", "mensaje": "Debe incluir zona horaria (ej. Z)."})
    if hasta.tzinfo is None:
        detalles.append({"campo": "query.hasta", "mensaje": "Debe incluir zona horaria (ej. Z)."})
    if detalles:
        raise ErrorValidacion("Las fechas deben estar en ISO 8601 con zona horaria.", detalles)
    if desde >= hasta:
        raise ErrorValidacion(
            "El intervalo es inválido: 'desde' debe ser anterior a 'hasta'.",
            [{"campo": "query.desde", "mensaje": "desde < hasta"}],
        )
    if hasta - desde > VENTANA_MAXIMA:
        raise ErrorValidacion(
            "El intervalo supera el máximo de 3 horas.",
            [{"campo": "query.hasta", "mensaje": "hasta - desde <= 3h"}],
        )


def tope_puntos(desde: datetime, hasta: datetime, resolucion: Resolucion, equipos: int) -> int:
    """Cantidad máxima de ventanas que puede devolver la consulta (RNF12)."""
    ventanas = math.ceil((hasta - desde).total_seconds() / SEGUNDOS_RESOLUCION[resolucion]) + 1
    return ventanas * equipos


class EstadisticasService:
    def __init__(self, influx: Any):
        self._influx = influx

    def consultar(
        self,
        codigo: str,
        desde: datetime,
        hasta: datetime,
        resolucion: Resolucion,
        equipo: str | None,
    ) -> EstadisticasPartido:
        validar_intervalo(desde, hasta)
        tope = tope_puntos(desde, hasta, resolucion, 1 if equipo else 2)
        filas = self._influx.serie_partido(codigo, equipo, desde, hasta, resolucion.value, tope)

        series: dict[str, list[dict[str, Any]]] = {}
        for fila in filas:
            series.setdefault(fila.pop("equipo_id"), []).append(fila)
        return EstadisticasPartido(
            codigo_partido=codigo,
            desde=desde,
            hasta=hasta,
            resolucion=resolucion,
            series=[SerieEquipo(equipo=eq, puntos=puntos) for eq, puntos in series.items()],
        )

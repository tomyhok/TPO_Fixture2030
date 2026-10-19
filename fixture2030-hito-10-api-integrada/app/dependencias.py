"""Composición de la aplicación: crea adaptadores y servicios y los entrega a las rutas.

Las rutas solo conocen servicios; los servicios solo conocen adaptadores; los
adaptadores son los únicos que importan drivers. Las pruebas unitarias
reemplazan los adaptadores por dobles en memoria con `crear_app(adaptadores=...)`.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app import VERSION
from app.config.settings import Settings
from app.services.actas_service import ActasService
from app.services.comentarios_service import ComentariosService
from app.services.equipos_service import EquiposService
from app.services.estadisticas_service import EstadisticasService
from app.services.idempotencia import Idempotencia
from app.services.partidos_service import PartidosService
from app.services.salud_service import SaludService
from app.services.sesiones_service import SesionesService


@dataclass
class Adaptadores:
    mongodb: Any
    neo4j: Any
    cassandra: Any
    redis: Any
    influxdb: Any
    iris: Any

    def como_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    def cerrar(self) -> None:
        for adaptador in self.como_dict().values():
            try:
                adaptador.cerrar()
            except Exception:  # noqa: BLE001 - el cierre no debe impedir apagar la API
                pass


@dataclass
class Servicios:
    equipos: EquiposService
    partidos: PartidosService
    comentarios: ComentariosService
    sesiones: SesionesService
    estadisticas: EstadisticasService
    actas: ActasService
    salud: SaludService


def crear_adaptadores(settings: Settings) -> Adaptadores:
    # Importación diferida: las pruebas unitarias no necesitan los drivers.
    from app.adapters.cassandra_adapter import CassandraAdapter
    from app.adapters.influx_adapter import InfluxAdapter
    from app.adapters.iris_adapter import IrisAdapter
    from app.adapters.mongo_adapter import MongoAdapter
    from app.adapters.neo4j_adapter import Neo4jAdapter
    from app.adapters.redis_adapter import RedisAdapter

    return Adaptadores(
        mongodb=MongoAdapter(settings),
        neo4j=Neo4jAdapter(settings),
        cassandra=CassandraAdapter(settings),
        redis=RedisAdapter(settings),
        influxdb=InfluxAdapter(settings),
        iris=IrisAdapter(settings),
    )


def crear_servicios(a: Adaptadores, settings: Settings) -> Servicios:
    idempotencia = Idempotencia(a.redis, settings.idempotencia_ttl_s)
    return Servicios(
        equipos=EquiposService(a.mongodb, a.neo4j),
        partidos=PartidosService(a.neo4j, a.redis, settings.cache_partido_ttl_s),
        comentarios=ComentariosService(a.cassandra, a.neo4j, idempotencia),
        sesiones=SesionesService(a.redis),
        estadisticas=EstadisticasService(a.influxdb),
        actas=ActasService(a.iris, idempotencia),
        salud=SaludService(
            a.como_dict(),
            faltantes=settings.configuracion_faltante(),
            ttl_cache_s=settings.health_cache_ttl_s,
            umbral_lento_ms=settings.health_umbral_lento_ms,
            version=VERSION,
        ),
    )


def servicios(request: Request) -> Servicios:
    return request.app.state.servicios

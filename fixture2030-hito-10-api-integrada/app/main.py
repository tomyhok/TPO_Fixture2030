"""Punto de entrada de la API REST integrada del Fixture 2030 (Hito 10).

    uvicorn app.main:app --host 127.0.0.1 --port 8000

Swagger UI: http://localhost:8000/docs   ·   OpenAPI: http://localhost:8000/openapi.json
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import VERSION
from app.config.settings import Settings, obtener_settings
from app.core.http import instalar_manejadores, instalar_middleware, instalar_openapi
from app.core.observabilidad import configurar_logs, logger
from app.dependencias import Adaptadores, crear_adaptadores, crear_servicios
from app.routes import actas, comentarios, equipos, estadisticas, partidos, salud, sesiones


DESCRIPCION = """Seis lecturas representativas, una por motor: MongoDB, Neo4j,
Cassandra, Redis, InfluxDB e IRIS. Contratos, validación y errores uniformes.
La API no escribe datos de dominio. Los endpoints de salud corresponden al Hito 11.
Todas las respuestas incluyen X-Request-ID. Laboratorio local sin autenticación HTTP."""

TAGS = []


def crear_app(adaptadores: Adaptadores | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or obtener_settings()
    configurar_logs(settings.log_level)
    log = logger("app")

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        propios = adaptadores or crear_adaptadores(settings)
        app.state.servicios = crear_servicios(propios, settings)
        log.info("api_iniciada version=%s", VERSION)
        yield
        propios.cerrar()
        log.info("api_detenida")

    app = FastAPI(
        title="Fixture 2030 - API REST integrada",
        version=VERSION,
        description=DESCRIPCION,
        openapi_tags=TAGS,
        servers=[{"url": f"http://localhost:{settings.api_port}", "description": "Notebook (local)"}],
        lifespan=ciclo_de_vida,
    )
    instalar_middleware(app)
    instalar_manejadores(app)
    for modulo in (equipos, partidos, comentarios, sesiones, estadisticas, actas, salud):
        app.include_router(modulo.router)
    instalar_openapi(app)
    return app


app = crear_app()

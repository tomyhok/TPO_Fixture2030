"""Punto de entrada de la API REST integrada del Fixture 2030 (Hito 10).

    uvicorn app.main:app --host 127.0.0.1 --port 8000

Swagger UI: http://localhost:8000/docs   ·   OpenAPI: http://localhost:8000/openapi.json
"""

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import VERSION
from app.config.settings import Settings, obtener_settings
from app.core.http import instalar_manejadores, instalar_middleware, instalar_openapi
from app.core.logs_cassandra import CassandraLogHandler, PersistorLogsCassandra
from app.core.observabilidad import configurar_logs, desinstalar_handler_logs, instalar_handler_logs, logger
from app.dependencias import Adaptadores, crear_adaptadores, crear_servicios
from app.routes import comentarios, equipos, estadisticas, logs, partidos, portal, salud, sesiones


DESCRIPCION = """Cinco lecturas representativas, una por motor: MongoDB, Neo4j,
Cassandra, Redis e InfluxDB. Contratos, validación y errores uniformes.
Estas rutas no escriben datos de dominio; el portal de demostración (/portal, fuera
de este contrato) agrega escrituras acotadas en MongoDB, Neo4j, Redis y Cassandra.
Los endpoints de salud corresponden al Hito 11.
Todas las respuestas incluyen X-Request-ID. Laboratorio local sin autenticación HTTP."""

TAGS = []
DIR_FRONT = Path(__file__).parent / "front"
# Windows no siempre registra .webp (logo del portal): sin esto se sirve como octet-stream.
mimetypes.add_type("image/webp", ".webp")


def crear_app(adaptadores: Adaptadores | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or obtener_settings()
    configurar_logs(settings.log_level)
    log = logger("app")

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        propios = adaptadores or crear_adaptadores(settings)
        app.state.servicios = crear_servicios(propios, settings)
        persistor_logs: PersistorLogsCassandra | None = None
        handler_logs: CassandraLogHandler | None = None
        if settings.logs_cassandra_enabled and hasattr(propios.cassandra, "escribir_lote_logs"):
            persistor_logs = PersistorLogsCassandra(
                escritor=propios.cassandra,
                servicio=settings.logs_cassandra_servicio,
                queue_size=settings.logs_cassandra_queue_size,
                batch_size=settings.logs_cassandra_batch_size,
                flush_interval_s=settings.logs_cassandra_flush_interval_s,
                ttl_s=settings.logs_cassandra_ttl_s,
            )
            persistor_logs.iniciar()
            handler_logs = CassandraLogHandler(
                persistor_logs,
                servicio=settings.logs_cassandra_servicio,
            )
            instalar_handler_logs(handler_logs)
        app.state.persistor_logs = persistor_logs
        log.info("api_iniciada version=%s", VERSION)
        try:
            yield
        finally:
            app.state.servicios.simulador.cerrar()  # detiene las simulaciones antes de cerrar las bases
            log.info("api_detenida")
            if handler_logs is not None:
                desinstalar_handler_logs(handler_logs)
            if persistor_logs is not None:
                persistor_logs.cerrar(timeout_s=2.0)
            propios.cerrar()

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
    for modulo in (equipos, partidos, comentarios, sesiones, estadisticas, salud, logs):
        app.include_router(modulo.router)
    # Portal del Fixture (/portal) y diagrama de integración (/demo): páginas estáticas
    # que consumen la API desde el navegador. Las rutas /portal/api quedan fuera de OpenAPI.
    app.include_router(portal.router)
    app.include_router(portal.raiz)
    app.mount("/portal", StaticFiles(directory=DIR_FRONT / "portal", html=True), name="portal")
    app.mount("/demo", StaticFiles(directory=DIR_FRONT / "demo", html=True), name="demo")
    instalar_openapi(app)
    return app


app = crear_app()

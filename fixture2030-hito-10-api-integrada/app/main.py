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


DESCRIPCION = """
API REST que integra los módulos NoSQL del Fixture Mundial 2030. Cada ruta resuelve un
caso de uso documentado en `docs/casos_de_uso.md` y llega a la fuente que le corresponde
mediante un adaptador propio:

| Módulo | Fuente | Hito |
|---|---|---|
| Equipos y jugadores | MongoDB | 4 |
| Partidos, eventos y relaciones | Neo4j | 5 |
| Comentarios | Cassandra | 6 |
| Sesiones y caché | Redis | 7 |
| Estadísticas temporales | InfluxDB 3 | 8 |
| Actas oficiales | InterSystems IRIS | 9 |

**Errores.** Todas las respuestas de error usan el esquema `ErrorRespuesta`. Toda respuesta
incluye el header `X-Request-ID` (se reutiliza el que envía el cliente si es válido), que
también aparece en los logs de la ruta y del adaptador.

**Autenticación.** No implementada en este hito: la API se ejecuta en el laboratorio local.
"""

TAGS = [
    {"name": "Equipos y jugadores (MongoDB)", "description": "Colecciones `equipos` y `jugadores` (Hito 4)."},
    {"name": "Partidos y relaciones (Neo4j)", "description": "Grafo de partidos, equipos, sedes y eventos (Hito 5)."},
    {"name": "Comentarios (Cassandra)", "description": "Muro por partición y publicación (Hito 6)."},
    {"name": "Sesiones (Redis)", "description": "Sesiones con TTL (Hito 7)."},
    {"name": "Estadísticas (InfluxDB)", "description": "Ventanas temporales agregadas (Hito 8)."},
    {"name": "Actas oficiales (IRIS)", "description": "Entidad compleja con transiciones validadas (Hito 9)."},
    {
        "name": "Salud",
        "description": "Liveness, readiness y diagnóstico de conectividad por fuente (Hitos 10 y 11).",
    },
]


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

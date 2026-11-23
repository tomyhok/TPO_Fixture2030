"""Piezas HTTP transversales: request ID, log de acceso, formato de error y OpenAPI."""

import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errores import (
    DependenciaNoDisponible,
    DependenciaTimeout,
    ErrorAPI,
    ErrorInterno,
    ErrorValidacion,
    MetodoNoPermitido,
    RecursoNoEncontrado,
)
from app.core.metricas import metricas
from app.core.observabilidad import logger, nuevo_request_id, request_id_actual
from app.schemas.comunes import ErrorRespuesta

_log_acceso = logger("acceso")
_log_error = logger("error")

HEADER_REQUEST_ID = "X-Request-ID"


def _ruta_plantilla(request: Request) -> str:
    ruta = getattr(request.scope.get("route"), "path", None)
    return str(ruta) if ruta else request.url.path


def respuesta_error(error: ErrorAPI, request: Request | None = None) -> JSONResponse:
    if request is not None:
        request.state.error_codigo = error.codigo
    cuerpo = {
        "error": {
            "codigo": error.codigo,
            "mensaje": error.mensaje,
            "request_id": request_id_actual.get(),
            "detalles": error.detalles,
        }
    }
    return JSONResponse(status_code=error.status_http, content=cuerpo)


def instalar_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_y_acceso(request: Request, call_next: Any) -> Any:
        request_id = nuevo_request_id(request.headers.get(HEADER_REQUEST_ID))
        token = request_id_actual.set(request_id)
        es_metricas = request.url.path == "/metrics"
        if not es_metricas:
            metricas.iniciar_request()
        inicio = time.perf_counter()
        try:
            respuesta = await call_next(request)
        except Exception:  # noqa: BLE001 - último recurso: error interno seguro
            _log_error.exception(
                "metodo=%s ruta=%s resultado=excepcion_no_controlada", request.method, request.url.path
            )
            respuesta = respuesta_error(ErrorInterno(), request)
        duracion_s = time.perf_counter() - inicio
        duracion_ms = duracion_s * 1000
        if not es_metricas:
            ruta_norm = _ruta_plantilla(request)
            metricas.finalizar_request(request.method, ruta_norm, respuesta.status_code, duracion_s)
            codigo_err = getattr(request.state, "error_codigo", None)
            if codigo_err:
                metricas.registrar_error_http(request.method, ruta_norm, codigo_err)
        respuesta.headers[HEADER_REQUEST_ID] = request_id
        # Solo método, ruta, estado y duración: nunca cuerpos ni query strings.
        _log_acceso.info(
            "metodo=%s ruta=%s estado=%s duracion_ms=%.1f",
            request.method,
            request.url.path,
            respuesta.status_code,
            duracion_ms,
        )
        request_id_actual.reset(token)
        return respuesta


def instalar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorAPI)
    async def _error_api(request: Request, exc: ErrorAPI) -> JSONResponse:
        return respuesta_error(exc, request)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalles = [
            {"campo": ".".join(str(p) for p in e.get("loc", ())), "mensaje": e.get("msg", "")}
            for e in exc.errors()
        ]
        return respuesta_error(
            ErrorValidacion("La solicitud tiene parámetros o cuerpo inválidos.", detalles), request
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return respuesta_error(RecursoNoEncontrado("La ruta solicitada no existe."), request)
        if exc.status_code == 405:
            return respuesta_error(MetodoNoPermitido("El método no está permitido para esta ruta."), request)
        return respuesta_error(ErrorInterno(), request)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        _log_error.exception("metodo=%s ruta=%s resultado=error_inesperado", request.method, request.url.path)
        return respuesta_error(ErrorInterno(), request)


# ----------------------------------------------------------------- OpenAPI
_DESCRIPCIONES = {
    400: "Validación: parámetro de ruta, query o cuerpo inválido. No se consulta ninguna base.",
    404: "Recurso inexistente.",
    500: "Error interno seguro: el detalle técnico queda solo en el log.",
    503: "Una fuente de datos no está disponible.",
    504: "Una fuente de datos no respondió dentro del timeout.",
}

_EJEMPLOS = {
    400: ErrorValidacion(
        "La solicitud tiene parámetros o cuerpo inválidos.",
        [{"campo": "path.codigo_iso", "mensaje": "String should match pattern '^[A-Z]{3}$'"}],
    ),
    404: RecursoNoEncontrado("No existe la selección 'XYZ'."),
    500: ErrorInterno(),
    503: DependenciaNoDisponible("mongodb"),
    504: DependenciaTimeout("neo4j"),
}


def respuestas(*codigos: int, ejemplos: dict[int, ErrorAPI] | None = None) -> dict[int | str, dict[str, Any]]:
    """Documenta en OpenAPI los errores que una ruta puede producir, con el esquema común."""
    resultado: dict[int | str, dict[str, Any]] = {}
    for codigo in (400, *codigos, 500):
        ejemplo = (ejemplos or {}).get(codigo, _EJEMPLOS[codigo])
        resultado[codigo] = {
            "model": ErrorRespuesta,
            "description": _DESCRIPCIONES[codigo],
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "codigo": ejemplo.codigo,
                            "mensaje": ejemplo.mensaje,
                            "request_id": "7f3c1a2e-0b4d-4c55-9a51-2f0f3c9e8d10",
                            "detalles": ejemplo.detalles,
                        }
                    }
                }
            },
        }
    return resultado


def instalar_openapi(app: FastAPI) -> None:
    """La API responde 400 (no 422) a la validación: se quitan los 422 automáticos
    de FastAPI para que el contrato describa solo respuestas que existen."""

    def generar() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        esquema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
        )
        for ruta in esquema.get("paths", {}).values():
            for operacion in ruta.values():
                operacion.get("responses", {}).pop("422", None)
        componentes = esquema.get("components", {}).get("schemas", {})
        componentes.pop("HTTPValidationError", None)
        componentes.pop("ValidationError", None)
        app.openapi_schema = esquema
        return esquema

    app.openapi = generar  # type: ignore[method-assign]

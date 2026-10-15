"""Errores de la aplicación (RF11, RF12).

Los servicios y adaptadores solo lanzan estas excepciones. Cada una sabe qué
código HTTP y qué `codigo` de negocio le corresponde, de modo que el formato de
error es único para toda la API. El mensaje es siempre apto para el consumidor:
el detalle técnico (excepción del driver, consulta, host) solo va al log.
"""

from typing import Any


class ErrorAPI(Exception):
    status_http: int = 500
    codigo: str = "ERROR_INTERNO"

    def __init__(self, mensaje: str, detalles: list[dict[str, Any]] | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or []


class ErrorValidacion(ErrorAPI):
    status_http = 400
    codigo = "VALIDACION"


class RecursoNoEncontrado(ErrorAPI):
    status_http = 404
    codigo = "RECURSO_NO_ENCONTRADO"


class SesionNoVigente(ErrorAPI):
    status_http = 404
    codigo = "SESION_NO_VIGENTE"


class MetodoNoPermitido(ErrorAPI):
    status_http = 405
    codigo = "METODO_NO_PERMITIDO"


class ConflictoEstado(ErrorAPI):
    status_http = 409
    codigo = "CONFLICTO_ESTADO"


class ConflictoIdempotencia(ErrorAPI):
    status_http = 409
    codigo = "CONFLICTO_IDEMPOTENCIA"


class ErrorInterno(ErrorAPI):
    status_http = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje: str = "Ocurrió un error inesperado. Informe el request_id."):
        super().__init__(mensaje)


class ErrorDependencia(ErrorAPI):
    """Base de las fallas de una fuente de datos."""

    def __init__(self, dependencia: str, mensaje: str):
        super().__init__(mensaje, [{"dependencia": dependencia}])
        self.dependencia = dependencia


class DependenciaNoDisponible(ErrorDependencia):
    status_http = 503
    codigo = "DEPENDENCIA_NO_DISPONIBLE"

    def __init__(self, dependencia: str):
        super().__init__(dependencia, f"La fuente de datos '{dependencia}' no está disponible.")


class DependenciaTimeout(ErrorDependencia):
    status_http = 504
    codigo = "DEPENDENCIA_TIMEOUT"

    def __init__(self, dependencia: str):
        super().__init__(
            dependencia, f"La fuente de datos '{dependencia}' no respondió dentro del tiempo límite."
        )

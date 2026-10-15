"""Casos de uso CU13–CU15 (acta oficial en IRIS).

La fachada de IRIS informa el resultado de negocio con un código; este
servicio lo convierte en la respuesta o el error del contrato:

  NO_ENCONTRADO        -> 404 RECURSO_NO_ENCONTRADO
  TRANSICION_INVALIDA  -> 409 CONFLICTO_ESTADO
  PARTIDO_FINALIZADO   -> 409 CONFLICTO_ESTADO
  VALIDACION           -> 400 VALIDACION (rechazo del modelo de objetos)
  otro                 -> 500 ERROR_INTERNO
"""

from typing import Any

from app.core.errores import (
    ConflictoEstado,
    ErrorAPI,
    ErrorInterno,
    ErrorValidacion,
    RecursoNoEncontrado,
)
from app.schemas.actas import (
    Acta,
    EstadoPartido,
    EventoNuevo,
    EventoRegistrado,
    ResultadoCambioEstado,
)
from app.services.idempotencia import Idempotencia


def _error(resultado: dict[str, Any], codigo: str, estado_pedido: str | None = None) -> ErrorAPI:
    tipo = resultado.get("error")
    if tipo == "NO_ENCONTRADO":
        return RecursoNoEncontrado(f"No existe el acta del partido '{codigo}'.")
    if tipo == "TRANSICION_INVALIDA":
        return ConflictoEstado(
            f"No se puede pasar de '{resultado['estado_actual']}' a '{estado_pedido}'. "
            "Transiciones permitidas: Programado -> En Juego -> Finalizado.",
            [{"estado_actual": resultado["estado_actual"], "estado_pedido": estado_pedido}],
        )
    if tipo == "PARTIDO_FINALIZADO":
        return ConflictoEstado(
            "El partido está Finalizado: el acta no admite eventos nuevos.",
            [{"estado_actual": "Finalizado"}],
        )
    if tipo == "VALIDACION":
        return ErrorValidacion("El modelo de objetos rechazó los datos del evento.")
    return ErrorInterno()


class ActasService:
    def __init__(self, iris: Any, idempotencia: Idempotencia):
        self._iris = iris
        self._idempotencia = idempotencia

    def obtener(self, codigo: str) -> Acta:
        resultado = self._iris.obtener_acta(codigo)
        if not resultado.get("ok"):
            raise _error(resultado, codigo)
        return Acta.model_validate(resultado["acta"])

    def cambiar_estado(self, codigo: str, estado: EstadoPartido) -> ResultadoCambioEstado:
        resultado = self._iris.cambiar_estado(codigo, estado.value)
        if not resultado.get("ok"):
            raise _error(resultado, codigo, estado.value)
        return ResultadoCambioEstado(cambiado=bool(resultado["cambiado"]), acta=resultado["acta"])

    def registrar_evento(
        self, codigo: str, nuevo: EventoNuevo, clave_idempotencia: str
    ) -> tuple[EventoRegistrado, bool]:
        cuerpo = {"codigo_partido": codigo, **nuevo.model_dump(mode="json")}

        def escribir() -> dict[str, Any]:
            resultado = self._iris.registrar_evento(codigo, nuevo.minuto, nuevo.tipo.value, nuevo.descripcion)
            if not resultado.get("ok"):
                raise _error(resultado, codigo)
            registrado = EventoRegistrado(
                codigo_partido=codigo, evento=resultado["evento"], acta=resultado["acta"]
            )
            return registrado.model_dump(mode="json")

        respuesta, repetida = self._idempotencia.ejecutar("evento_acta", clave_idempotencia, cuerpo, escribir)
        return EventoRegistrado.model_validate(respuesta), repetida

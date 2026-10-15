"""Parámetros de ruta reutilizables: el formato se valida antes de tocar una base (RF10)."""

from typing import Annotated

from fastapi import Header, Path

from app.schemas.comunes import (
    PATRON_CODIGO_ISO,
    PATRON_CODIGO_PARTIDO,
    PATRON_ID_JUGADOR,
    PATRON_ID_SESION,
    PATRON_UUID,
)

CodigoIso = Annotated[
    str, Path(pattern=PATRON_CODIGO_ISO, description="Código de la selección (3 letras).", examples=["ARG"])
]
IdJugador = Annotated[
    str, Path(pattern=PATRON_ID_JUGADOR, description="Identificador del jugador.", examples=["ARG-10"])
]
CodigoPartido = Annotated[
    str, Path(pattern=PATRON_CODIGO_PARTIDO, description="Código de negocio del partido.", examples=["P-001"])
]
IdSesion = Annotated[
    str, Path(pattern=PATRON_ID_SESION, description="Identificador opaco de la sesión.", examples=["S-0001"])
]
ClaveIdempotencia = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        pattern=PATRON_UUID,
        description="UUID generado por el cliente. Reintentar con la misma clave no duplica la escritura.",
        examples=["3f2b8c1e-6d4a-4e2b-9c7d-1a2b3c4d5e6f"],
    ),
]

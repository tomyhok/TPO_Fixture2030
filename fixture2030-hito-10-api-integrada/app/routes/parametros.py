"""Parámetros de ruta reutilizables: el formato se valida antes de tocar una base (RF10)."""

from typing import Annotated

from fastapi import Path

from app.schemas.comunes import (
    PATRON_CODIGO_ISO,
    PATRON_CODIGO_PARTIDO,
    PATRON_ID_SESION,
)

CodigoIso = Annotated[
    str, Path(pattern=PATRON_CODIGO_ISO, description="Código de la selección (3 letras).", examples=["ARG"])
]
CodigoPartido = Annotated[
    str, Path(pattern=PATRON_CODIGO_PARTIDO, description="Código de negocio del partido.", examples=["P-001"])
]
IdSesion = Annotated[
    str, Path(pattern=PATRON_ID_SESION, description="Identificador opaco de la sesión.", examples=["S-0001"])
]

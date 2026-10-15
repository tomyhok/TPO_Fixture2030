"""Contratos del módulo de sesiones (Redis)."""

from pydantic import ConfigDict, Field

from app.schemas.comunes import Modelo


class Sesion(Modelo):
    """Vista pública de la sesión: no incluye dispositivo, páginas vistas ni marcas internas."""

    id_sesion: str
    usuario_id: str | None
    rol: str | None
    estado: str | None
    ttl_restante_s: int | None = Field(description="Segundos hasta que la sesión expire.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_sesion": "S-0001",
                "usuario_id": "U-0001",
                "rol": "fan",
                "estado": "activa",
                "ttl_restante_s": 1712,
            }
        }
    )

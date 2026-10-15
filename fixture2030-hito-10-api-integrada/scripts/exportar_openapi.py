"""Genera openapi/openapi.yaml a partir de la aplicación (RNF2).

El contrato se deriva del código (rutas, validaciones y schemas Pydantic), así
que no puede describir endpoints que no existen. La prueba
tests/unit/test_contrato_openapi.py falla si el archivo queda desactualizado.

Uso (desde fixture2030-hito-10-api-integrada/):
    .venv/Scripts/python scripts/exportar_openapi.py
"""

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.config.settings import Settings  # noqa: E402
from app.main import crear_app  # noqa: E402


def main() -> None:
    esquema = crear_app(adaptadores=object(), settings=Settings(_env_file=None)).openapi()  # type: ignore[arg-type]
    destino = RAIZ / "openapi" / "openapi.yaml"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(
        yaml.safe_dump(esquema, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"Contrato escrito en {destino.relative_to(RAIZ)} ({len(esquema['paths'])} rutas)")


if __name__ == "__main__":
    main()

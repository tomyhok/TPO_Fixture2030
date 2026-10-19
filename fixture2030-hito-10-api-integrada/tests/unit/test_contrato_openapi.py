"""RNF2: el archivo openapi/openapi.yaml coincide con la API implementada.

Si una ruta, parámetro, schema o código cambia en el código y no se regenera
el contrato (`python scripts/exportar_openapi.py`), esta prueba falla.
"""

from pathlib import Path

import yaml

from app.config.settings import Settings
from app.main import crear_app

ARCHIVO = Path(__file__).resolve().parents[2] / "openapi" / "openapi.yaml"

RUTAS_ESPERADAS = {
    ("get", "/equipos"),
    ("get", "/equipos/{codigo_iso}"),
    ("get", "/equipos/{codigo_iso}/jugadores"),
    ("get", "/jugadores/{id_jugador}"),
    ("get", "/partidos/{codigo_partido}"),
    ("get", "/partidos/{codigo_partido}/eventos"),
    ("get", "/equipos/{codigo_iso}/rivales"),
    ("get", "/partidos/{codigo_partido}/comentarios"),
    ("post", "/partidos/{codigo_partido}/comentarios"),
    ("get", "/sesiones/{id_sesion}"),
    ("delete", "/sesiones/{id_sesion}"),
    ("get", "/partidos/{codigo_partido}/estadisticas"),
    ("get", "/partidos-oficiales/{codigo_partido}"),
    ("patch", "/partidos-oficiales/{codigo_partido}/estado"),
    ("post", "/partidos-oficiales/{codigo_partido}/eventos"),
    ("get", "/health"),
    ("get", "/health/live"),
    ("get", "/health/ready"),
    ("get", "/health/dependencias"),
}


def _esquema() -> dict:
    return crear_app(adaptadores=object(), settings=Settings(_env_file=None)).openapi()  # type: ignore[arg-type]


def test_archivo_openapi_coincide_con_la_implementacion():
    assert ARCHIVO.exists(), "Falta openapi/openapi.yaml: ejecutar scripts/exportar_openapi.py"
    en_archivo = yaml.safe_load(ARCHIVO.read_text(encoding="utf-8"))
    assert en_archivo == _esquema(), "openapi.yaml desactualizado: ejecutar scripts/exportar_openapi.py"


def test_las_rutas_son_los_casos_de_uso_documentados():
    rutas = {(m, p) for p, ops in _esquema()["paths"].items() for m in ops}
    assert rutas == RUTAS_ESPERADAS


def test_no_se_documentan_respuestas_que_la_api_no_produce():
    esquema = _esquema()
    for operaciones in esquema["paths"].values():
        for operacion in operaciones.values():
            assert "422" not in operacion["responses"]
    assert "HTTPValidationError" not in esquema["components"]["schemas"]


def test_errores_documentados_usan_el_esquema_comun():
    for ruta, operaciones in _esquema()["paths"].items():
        if ruta.startswith("/health"):
            continue
        for operacion in operaciones.values():
            for codigo in ("400", "500"):
                assert codigo in operacion["responses"], (ruta, codigo)
            for codigo, respuesta in operacion["responses"].items():
                if codigo.startswith(("4", "5")):
                    ref = respuesta["content"]["application/json"]["schema"]["$ref"]
                    assert ref.endswith("/ErrorRespuesta")


def test_metadatos_minimos():
    esquema = _esquema()
    assert esquema["info"]["title"] and esquema["info"]["version"]
    assert esquema["servers"][0]["url"].startswith("http://localhost")
    assert len(esquema["tags"]) == 7

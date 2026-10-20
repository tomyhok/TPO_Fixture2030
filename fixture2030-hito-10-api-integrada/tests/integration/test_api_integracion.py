"""Lecturas reales; no carga ni reinicia datos desde las pruebas HTTP."""
import pytest
from tests.unit.test_api_esencial import RUTAS
pytestmark=pytest.mark.integracion
@pytest.mark.parametrize('fuente',list(RUTAS))
def test_lectura_real(cliente,settings,fuente):
    if settings.configuracion_faltante()[fuente]:
        pytest.skip(f"Configuración pendiente de {fuente}; no se cuenta como lectura exitosa.")
    ruta=RUTAS[fuente]
    if fuente=='iris': ruta='/partidos-oficiales/P-009'
    r=cliente.get(ruta)
    # La sesión de muestra puede haber vencido; eso no es desconexión.
    assert r.status_code in ((200,404) if fuente=='redis' else (200,)), r.text

"""Seis lecturas, contratos y errores esenciales; sin ampliar el dominio."""
import pytest
from app.core.errores import DependenciaNoDisponible, DependenciaTimeout
from tests.unit.conftest import sin_llamadas

RUTAS = {
 'mongodb':'/equipos/ARG', 'neo4j':'/partidos/P-001/eventos',
 'cassandra':'/partidos/P-001/comentarios?ventana=203006152016',
 'redis':'/sesiones/S-0001',
 'influxdb':'/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z',
 'iris':'/partidos-oficiales/P-001',
}

@pytest.mark.parametrize('fuente', list(RUTAS))
def test_lectura_usa_solo_su_fuente(cliente, adaptadores, fuente):
    r=cliente.get(RUTAS[fuente],headers={'X-Request-ID':'prueba-lectura'})
    assert r.status_code==200, r.text
    assert r.headers['x-request-id']=='prueba-lectura'
    assert adaptadores.como_dict()[fuente].llamadas
    assert all(not a.llamadas for n,a in adaptadores.como_dict().items() if n!=fuente)

@pytest.mark.parametrize('ruta', ['/equipos/XYZ','/partidos/P-999/eventos','/partidos-oficiales/P-999','/sesiones/S-9999'])
def test_ausencia_es_404(cliente,ruta):
    assert cliente.get(ruta).status_code==404

def test_coleccion_vacia_es_200(cliente):
    r=cliente.get('/partidos/P-002/eventos')
    assert r.status_code==200 and r.json()['eventos']==[]

@pytest.mark.parametrize('ruta', ['/equipos/arg','/partidos/P-001/eventos?limit=201',
 '/partidos/P-001/comentarios?ventana=203013152016',
 '/partidos/P-001/estadisticas?desde=2030-06-10T21:00:00Z&hasta=2030-06-10T20:00:00Z'])
def test_validacion_antes_de_consultar(cliente,adaptadores,ruta):
    assert cliente.get(ruta).status_code==400
    assert sin_llamadas(adaptadores)

@pytest.mark.parametrize('excepcion,status',[(DependenciaNoDisponible,503),(DependenciaTimeout,504)])
def test_error_dependencia_no_es_vacio_y_aisla_fuentes(cliente,adaptadores,excepcion,status):
    adaptadores.mongodb.falla=excepcion('mongodb')
    r=cliente.get('/equipos/ARG')
    assert r.status_code==status
    assert r.json()['error']['detalles']==[{'dependencia':'mongodb'}]
    assert cliente.get('/partidos/P-001/eventos').status_code==200

def test_openapi_solo_seis_lecturas_y_salud(cliente):
    from pathlib import Path
    import yaml
    paths=cliente.get('/openapi.json').json()['paths']
    negocios={p:v for p,v in paths.items() if not p.startswith('/health')}
    assert len(negocios)==6
    assert all(set(v)=={'get'} for v in negocios.values())
    assert cliente.post('/partidos/P-001/comentarios',json={}).status_code==405
    contrato=Path(__file__).resolve().parents[2]/'openapi/openapi.yaml'
    assert yaml.safe_load(contrato.read_text(encoding='utf-8'))['paths']==paths

"""Generador de la fase de grupos (scripts/datos/cargar_fase_grupos.py), sin Neo4j."""

import importlib.util
import json
from collections import Counter
from pathlib import Path

HITO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("cargar_fase_grupos", HITO / "scripts" / "datos" / "cargar_fase_grupos.py")
fase = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fase)

EQUIPOS = json.loads(fase.EQUIPOS_JSON.read_text(encoding="utf-8"))
PARTIDOS = fase.generar(EQUIPOS)
GRUPO = {e["_id"]: e["grupo"] for e in EQUIPOS}


def test_todos_contra_todos_por_grupo():
    assert len(PARTIDOS) == 96
    assert [p["codigo"] for p in PARTIDOS] == [f"P-{n:03d}" for n in range(3, 99)]
    cruces = Counter(frozenset((p["local"], p["visitante"])) for p in PARTIDOS)
    assert len(cruces) == 96 and set(cruces.values()) == {1}
    assert all(GRUPO[p["local"]] == GRUPO[p["visitante"]] == p["grupo"] for p in PARTIDOS)
    por_equipo = Counter(iso for p in PARTIDOS for iso in (p["local"], p["visitante"]))
    assert len(por_equipo) == 64 and set(por_equipo.values()) == {3}


def test_cada_seleccion_juega_una_vez_por_jornada_y_sedes_sin_choques():
    for jornada in (1, 2, 3):
        equipos = [iso for p in PARTIDOS if p["jornada"] == jornada for iso in (p["local"], p["visitante"])]
        assert len(equipos) == len(set(equipos)) == 64
    por_dia = Counter((p["fecha"], p["sede"]) for p in PARTIDOS)
    assert set(por_dia.values()) == {1}
    assert {p["fecha"] for p in PARTIDOS} <= {f"2030-06-{d}" for d in range(11, 27)}


def test_no_repite_los_partidos_de_muestra():
    cruces = {frozenset((p["local"], p["visitante"])) for p in PARTIDOS}
    assert frozenset(("ARG", "ESP")) not in cruces and frozenset(("URU", "ARG")) not in cruces


def test_listado_trae_goles_por_seleccion(cliente):
    p001 = next(p for p in cliente.get("/portal/api/partidos").json() if p["codigo_partido"] == "P-001")
    assert p001["goles"] == {"ARG": 1, "ESP": 0}

"""Carga en Neo4j la fase de grupos completa del Mundial 2030 para el portal.

Lee las 64 selecciones y su grupo del mismo JSON con que se cargaron MongoDB (Hito 4) y los
nodos Equipo de Neo4j (Hito 5), y arma un todos contra todos por grupo: 16 grupos x 6 partidos
= 96 partidos (P-003 a P-098), en tres fechas, con sede y árbitro.

Modelo que agrega al grafo del Hito 5:
    (:Grupo {letra})                              16 nodos
    (Equipo)-[:INTEGRA]->(Grupo)
    (Partido {codigo_partido, fecha, fase: 'Grupos', jornada, estado})-[:DEL_GRUPO]->(Grupo)
    (Equipo)-[:DISPUTA {condicion: 'local' | 'visitante'}]->(Partido)
    (Partido)-[:SE_JUEGA_EN]->(Sede)              12 sedes en los 6 países anfitriones
    (Arbitro)-[:DIRIGE]->(Partido)                12 árbitros (nombres ficticios)

Idempotente (MERGE): volver a correrlo no duplica nada ni cambia el estado de partidos ya
jugados; para eso está scripts/reiniciar_demo.py. P-001 y P-002 (muestra de los hitos 5 a 8)
no se tocan: enfrentan selecciones de grupos distintos.

Uso (desde fixture2030-hito-10-api-integrada/, con el .env configurado):
    .venv/Scripts/python scripts/datos/cargar_fase_grupos.py
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

HITO = Path(__file__).resolve().parents[2]
EQUIPOS_JSON = HITO.parent / "fixture2030-mongoDB" / "init-scripts" / "data" / "equipos.json"
PRIMER_CODIGO = 3  # P-001 y P-002 son la muestra de los hitos anteriores

# Todos contra todos de 4 equipos (cabezas de serie por ranking): (local, visitante) por jornada.
JORNADAS = [[(0, 1), (2, 3)], [(0, 2), (3, 1)], [(3, 0), (1, 2)]]
# Primer día de cada jornada; cada día juegan 4 grupos (A-D, E-H, I-L, M-P).
INICIO_JORNADA = [date(2030, 6, 11), date(2030, 6, 17), date(2030, 6, 23)]

SEDES = [
    ("MON", "Estadio Monumental", "Buenos Aires"),
    ("CEN", "Estadio Centenario", "Montevideo"),
    ("DCH", "Estadio Defensores del Chaco", "Asunción"),
    ("BER", "Estadio Santiago Bernabéu", "Madrid"),
    ("MET", "Estadio Metropolitano", "Madrid"),
    ("CNO", "Camp Nou", "Barcelona"),
    ("CAR", "Estadio La Cartuja", "Sevilla"),
    ("SMA", "San Mamés", "Bilbao"),
    ("LUZ", "Estádio da Luz", "Lisboa"),
    ("DRA", "Estádio do Dragão", "Oporto"),
    ("CAS", "Grand Stade Hassan II", "Casablanca"),
    ("RAB", "Estadio Príncipe Moulay Abdellah", "Rabat"),
]
# Nombres ficticios: no corresponden a árbitros reales.
ARBITROS = [
    ("40100201", "Diego", "Salvatierra", "FIFA"), ("40100202", "Ana Lucía", "Rojas", "FIFA"),
    ("40100203", "Pedro", "Henriques", "FIFA"), ("40100204", "Karim", "Benali", "FIFA"),
    ("40100205", "Tomás", "Ibarguren", "FIFA"), ("40100206", "Sofía", "Méndez", "FIFA"),
    ("40100207", "João", "Carvalho", "FIFA"), ("40100208", "Youssef", "Amrani", "FIFA"),
    ("40100209", "Lucas", "Vidal", "FIFA"), ("40100210", "Marta", "Echeverría", "FIFA"),
    ("40100211", "Henrik", "Larsen", "FIFA"), ("40100212", "Kenji", "Sato", "FIFA"),
]


def generar(equipos: list[dict]) -> list[dict]:
    """Partidos de la fase de grupos. Función pura: la prueban tests/unit/test_fase_grupos.py."""
    grupos: dict[str, list[dict]] = {}
    for e in equipos:
        grupos.setdefault(e["grupo"], []).append(e)
    letras = sorted(grupos)
    partidos = []
    n = PRIMER_CODIGO
    for j, jornada in enumerate(JORNADAS):
        for gi, letra in enumerate(letras):
            cabezas = sorted(grupos[letra], key=lambda e: e["ranking_fifa"])
            dia = INICIO_JORNADA[j] + timedelta(days=gi // 4)
            for k, (loc, vis) in enumerate(jornada):
                partidos.append({
                    "codigo": f"P-{n:03d}",
                    "grupo": letra,
                    "jornada": j + 1,
                    "fecha": dia.isoformat(),
                    "local": cabezas[loc]["_id"],
                    "visitante": cabezas[vis]["_id"],
                    # Cada grupo rota entre dos sedes vecinas de la lista.
                    "sede": SEDES[(2 * gi + k + j) % len(SEDES)][0],
                    "arbitro": ARBITROS[(n - PRIMER_CODIGO) % len(ARBITROS)][0],
                })
                n += 1
    return partidos


CYPHER = [
    ("restricciones", "CREATE CONSTRAINT grupo_letra IF NOT EXISTS FOR (g:Grupo) REQUIRE g.letra IS UNIQUE", None),
    ("restricciones", "CREATE CONSTRAINT arbitro_dni IF NOT EXISTS FOR (a:Arbitro) REQUIRE a.dni IS UNIQUE", None),
    ("sedes", """UNWIND $filas AS f MERGE (s:Sede {codigo_sede: f.codigo}) SET s.nombre = f.nombre, s.ciudad = f.ciudad""",
     "sedes"),
    ("árbitros", """UNWIND $filas AS f MERGE (a:Arbitro {dni: f.dni})
                   SET a.nombre = f.nombre, a.apellido = f.apellido, a.rango = f.rango""", "arbitros"),
    ("grupos", """UNWIND $filas AS f
                 MATCH (e:Equipo {codigo_iso: f.codigo_iso})
                 MERGE (g:Grupo {letra: f.grupo})
                 MERGE (e)-[:INTEGRA]->(g)""", "integrantes"),
    ("partidos", """UNWIND $filas AS f
                   MATCH (l:Equipo {codigo_iso: f.local}), (v:Equipo {codigo_iso: f.visitante})
                   MATCH (g:Grupo {letra: f.grupo}), (s:Sede {codigo_sede: f.sede}), (a:Arbitro {dni: f.arbitro})
                   MERGE (p:Partido {codigo_partido: f.codigo})
                   ON CREATE SET p.estado = 'Programado'
                   SET p.fecha = date(f.fecha), p.fase = 'Grupos', p.jornada = f.jornada
                   MERGE (l)-[:DISPUTA {condicion: 'local'}]->(p)
                   MERGE (v)-[:DISPUTA {condicion: 'visitante'}]->(p)
                   MERGE (p)-[:DEL_GRUPO]->(g)
                   MERGE (p)-[:SE_JUEGA_EN]->(s)
                   MERGE (a)-[:DIRIGE]->(p)""", "partidos"),
]


def main() -> int:
    sys.path.insert(0, str(HITO))
    from neo4j import GraphDatabase

    from app.config.settings import obtener_settings

    equipos = json.loads(EQUIPOS_JSON.read_text(encoding="utf-8"))
    partidos = generar(equipos)
    filas = {
        "sedes": [{"codigo": c, "nombre": n, "ciudad": ci} for c, n, ci in SEDES],
        "arbitros": [{"dni": d, "nombre": n, "apellido": a, "rango": r} for d, n, a, r in ARBITROS],
        "integrantes": [{"codigo_iso": e["_id"], "grupo": e["grupo"]} for e in equipos],
        "partidos": partidos,
    }
    s = obtener_settings()
    with GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password.get_secret_value())) as driver:
        with driver.session(database=s.neo4j_database) as sesion:
            for que, cypher, clave in CYPHER:
                sesion.run(cypher, {"filas": filas[clave]} if clave else {}).consume()
            total = sesion.run("MATCH (p:Partido)-[:DEL_GRUPO]->(:Grupo) RETURN count(p) AS n").single()["n"]
    print(f"Fase de grupos: {len(partidos)} partidos ({partidos[0]['codigo']} a {partidos[-1]['codigo']}), "
          f"{len(SEDES)} sedes, {len(ARBITROS)} árbitros. Partidos de grupo en Neo4j: {total}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

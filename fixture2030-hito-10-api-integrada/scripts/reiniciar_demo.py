"""Deja la demo del portal como al principio, para volver a presentarla.

  * Neo4j: borra los eventos simulados y la hora de inicio, y vuelve P-001 a 'En Juego' y todos
    los demás partidos (P-002 y la fase de grupos) a 'Programado'
    (scripts/datos/partidos_estado_arbitros.cypher).
  * Redis: borra el reloj de las simulaciones.
  * MongoDB: reabre el prode. Todas las predicciones quedan pendientes (sin puntos), se borran
    las liquidaciones y se rehace la tabla de posiciones.

No borra los mensajes del relator (Cassandra) ni las estadísticas simuladas (InfluxDB): el muro
muestra solo los últimos 15 minutos y cada simulación escribe en su propia ventana de tiempo.

Uso (desde fixture2030-hito-10-api-integrada/, con el .env configurado):
    .venv/Scripts/python scripts/reiniciar_demo.py
"""

import sys
from pathlib import Path

import redis
from neo4j import GraphDatabase

HITO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HITO))
from app.adapters.mongo_adapter import MongoAdapter  # noqa: E402
from app.config.settings import obtener_settings  # noqa: E402

CYPHER = HITO / "scripts" / "datos" / "partidos_estado_arbitros.cypher"


def sentencias(texto: str) -> list[str]:
    sin_comentarios = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


def main() -> int:
    s = obtener_settings()
    with GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password.get_secret_value())) as driver:
        with driver.session(database=s.neo4j_database) as sesion:
            for sentencia in sentencias(CYPHER.read_text(encoding="utf-8")):
                sesion.run(sentencia).consume()
    print("Neo4j: eventos simulados borrados; P-001 En Juego y el resto Programado")

    r = redis.Redis(host=s.redis_host, port=s.redis_port, db=s.redis_db,
                    password=s.redis_password.get_secret_value() or None)
    relojes = list(r.scan_iter("reloj:partido:*"))
    if relojes:
        r.delete(*relojes)
    r.close()
    print("Redis: reloj de la simulación borrado")

    mongo = MongoAdapter(s)
    try:
        n = mongo.reabrir_prode()
    finally:
        mongo.cerrar()
    print(f"MongoDB: prode reabierto ({n} predicciones vuelven a pendientes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

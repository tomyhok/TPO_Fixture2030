"""Adaptador de grafos: Neo4j (Hito 5).

Todas las consultas son Cypher fijo y parametrizado: el consumidor solo aporta
valores ($codigo, $limit), nunca fragmentos de consulta. Cada recorrido parte
de un nodo concreto buscado por su restricción de unicidad
(`partido_codigo`, `equipo_codigo_iso`) y tiene profundidad y cantidad
acotadas. Los nodos y relaciones se convierten a diccionarios simples; el
driver no sale de este módulo.
"""

from typing import Any

from neo4j import READ_ACCESS, GraphDatabase, Query
from neo4j import exceptions as neo4j_errors

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI

DEPENDENCIA = "neo4j"

CYPHER_EVENTOS_PARTIDO = """
MATCH (p:Partido {codigo_partido: $codigo})
OPTIONAL MATCH (ev:Evento)-[:CORRESPONDE_A]->(p)
WITH p, ev
ORDER BY ev.minuto, ev.id_evento
LIMIT $limit
OPTIONAL MATCH (j:Jugador)-[:PROTAGONIZA]->(ev)
WITH p, ev, head(collect(j)) AS j
ORDER BY ev.minuto, ev.id_evento
RETURN p.codigo_partido AS codigo_partido,
       collect(CASE WHEN ev IS NULL THEN NULL ELSE {
           id_evento: ev.id_evento,
           tipo: ev.tipo,
           minuto: ev.minuto,
           jugador: CASE WHEN j IS NULL THEN NULL
                    ELSE {id_jugador: j.id_jugador, nombre: j.nombre} END
       } END) AS eventos
"""

def _traducir(exc: Exception) -> ErrorAPI | None:
    codigo = getattr(exc, "code", "") or ""
    if "TransactionTimedOut" in codigo:
        return timeout(DEPENDENCIA)
    if codigo == "Neo.ClientError.Database.DatabaseNotFound":
        # NEO4J_DATABASE apunta a una base que no existe (contexto incorrecto, Hito 11).
        return no_disponible(DEPENDENCIA)
    if isinstance(
        exc,
        (
            neo4j_errors.ServiceUnavailable,
            neo4j_errors.SessionExpired,
            neo4j_errors.AuthError,
            neo4j_errors.DatabaseUnavailable,
            OSError,
        ),
    ):
        return no_disponible(DEPENDENCIA)
    return None


class Neo4jAdapter:
    def __init__(self, settings: Settings):
        # El driver crea las conexiones bajo demanda: no falla si Neo4j está caído.
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            connection_timeout=settings.timeout_conexion_s,
            connection_acquisition_timeout=settings.timeout_conexion_s + settings.timeout_operacion_s,
            max_connection_pool_size=20,
            user_agent="fixture2030-api",
        )
        self._database = settings.neo4j_database
        self._timeout = settings.timeout_operacion_s

    def _una_fila(self, nombre: str, cypher: str, parametros: dict[str, Any]) -> dict[str, Any] | None:
        """Ejecuta una lectura auto-commit (sin reintentos ocultos) con timeout."""
        with operacion(DEPENDENCIA, nombre, _traducir):
            with self._driver.session(
                database=self._database, default_access_mode=READ_ACCESS
            ) as sesion:
                registro = sesion.run(Query(cypher, timeout=self._timeout), parametros).single()
                return registro.data() if registro else None

    def eventos_partido(self, codigo: str, limit: int) -> dict[str, Any] | None:
        """None = el partido no existe; lista vacía = partido sin eventos."""
        return self._una_fila("partido.eventos", CYPHER_EVENTOS_PARTIDO, {"codigo": codigo, "limit": limit})

    def ping(self) -> None:
        self._una_fila("ping", "RETURN 1 AS ok", {})

    def cerrar(self) -> None:
        self._driver.close()

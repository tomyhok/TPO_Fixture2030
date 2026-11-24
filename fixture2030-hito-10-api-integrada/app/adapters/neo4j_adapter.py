"""Adaptador de grafos: Neo4j (Hito 5).

Todas las consultas son Cypher fijo y parametrizado: el consumidor solo aporta
valores ($codigo, $limit), nunca fragmentos de consulta. Cada recorrido parte
de un nodo concreto buscado por su restricción de unicidad
(`partido_codigo`, `equipo_codigo_iso`) y tiene profundidad y cantidad
acotadas. Los nodos y relaciones se convierten a diccionarios simples; el
driver no sale de este módulo.
"""

from typing import Any

from neo4j import READ_ACCESS, WRITE_ACCESS, GraphDatabase, Query
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

# Fixture completo en una consulta: sede, árbitro, grupo, selecciones y, para el marcador,
# la selección de cada gol (prefijo de id_jugador, mismo criterio que el portal y el prode).
CYPHER_PARTIDOS = """
MATCH (p:Partido)
OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)
OPTIONAL MATCH (a:Arbitro)-[:DIRIGE]->(p)
OPTIONAL MATCH (p)-[:DEL_GRUPO]->(g:Grupo)
WITH p, head(collect(s)) AS s, head(collect(a)) AS a, head(collect(g.letra)) AS grupo
OPTIONAL MATCH (e:Equipo)-[d:DISPUTA]->(p)
WITH p, s, a, grupo, collect(CASE WHEN e IS NULL THEN NULL ELSE
     {codigo_iso: e.codigo_iso, nombre: e.nombre, condicion: d.condicion} END) AS equipos
OPTIONAL MATCH (jg:Jugador)-[:PROTAGONIZA]->(ev:Evento)-[:CORRESPONDE_A]->(p)
WHERE toLower(ev.tipo) STARTS WITH 'gol'
WITH p, s, a, grupo, equipos, collect(split(jg.id_jugador, '-')[0]) AS goleadores
RETURN p.codigo_partido AS codigo_partido, toString(p.fecha) AS fecha, p.fase AS fase,
       grupo, p.jornada AS jornada,
       coalesce(p.estado, $estado_inicial) AS estado, toString(p.inicio) AS inicio,
       CASE WHEN s IS NULL THEN NULL ELSE {nombre: s.nombre, ciudad: s.ciudad} END AS sede,
       CASE WHEN a IS NULL THEN NULL ELSE {nombre: a.nombre, apellido: a.apellido, rango: a.rango} END AS arbitro,
       equipos, goleadores
ORDER BY fecha, codigo_partido
LIMIT 300
"""

# Cambio de estado condicionado al estado leído: si otro cliente lo cambió en el medio,
# no se pisa (no devuelve fila) y la API responde 409.
CYPHER_CAMBIAR_ESTADO = """
MATCH (p:Partido {codigo_partido: $codigo})
WHERE coalesce(p.estado, $estado_inicial) = $actual
SET p.estado = $nuevo, p.inicio = coalesce(datetime($inicio), p.inicio)
RETURN p.estado AS estado
"""

CYPHER_JUGADORES_PARTIDO = """
MATCH (e:Equipo)-[:DISPUTA]->(:Partido {codigo_partido: $codigo})
MATCH (j:Jugador)-[:PERTENECE_A]->(e)
RETURN e.codigo_iso AS codigo_iso, j.id_jugador AS id_jugador, j.nombre AS nombre, j.posicion AS posicion
ORDER BY codigo_iso, id_jugador
LIMIT 200
"""

# Evento de la simulación: mismo modelo del Hito 5 ((Jugador)-[:PROTAGONIZA]->(Evento)
# -[:CORRESPONDE_A]->(Partido)) con la marca `simulado`, que permite borrarlos al reiniciar.
CYPHER_REGISTRAR_EVENTO = """
MATCH (p:Partido {codigo_partido: $codigo})
MATCH (j:Jugador {id_jugador: $id_jugador})
CREATE (ev:Evento {id_evento: $id_evento, tipo: $tipo, minuto: $minuto, simulado: true})
CREATE (ev)-[:CORRESPONDE_A]->(p)
CREATE (j)-[:PROTAGONIZA]->(ev)
"""
ESTADO_INICIAL = "Programado"


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

    def listar_partidos(self) -> list[dict[str, Any]]:
        """Portal: el fixture completo con estado, sede, árbitro, grupo, selecciones y goles
        (SE_JUEGA_EN, DIRIGE, DEL_GRUPO, DISPUTA y PROTAGONIZA). Sin estado cargado = Programado."""
        with operacion(DEPENDENCIA, "partido.listar", _traducir):
            with self._driver.session(
                database=self._database, default_access_mode=READ_ACCESS
            ) as sesion:
                resultado = sesion.run(Query(CYPHER_PARTIDOS, timeout=self._timeout),
                                       {"estado_inicial": ESTADO_INICIAL})
                filas = [r.data() for r in resultado]
        for f in filas:
            goles = {e["codigo_iso"]: 0 for e in f["equipos"]}
            for iso in f.pop("goleadores"):
                goles[iso] = goles.get(iso, 0) + 1
            f["goles"] = goles
        return filas

    def cambiar_estado(self, codigo: str, actual: str, nuevo: str, inicio: str | None = None) -> bool:
        """Escritura auto-commit, sin reintentos ocultos. False si el estado ya no era `actual`.
        `inicio` (ISO 8601 UTC) registra la hora real en que arrancó el partido."""
        with operacion(DEPENDENCIA, "partido.cambiar_estado", _traducir):
            with self._driver.session(
                database=self._database, default_access_mode=WRITE_ACCESS
            ) as sesion:
                fila = sesion.run(
                    Query(CYPHER_CAMBIAR_ESTADO, timeout=self._timeout),
                    {"codigo": codigo, "actual": actual, "nuevo": nuevo, "inicio": inicio,
                     "estado_inicial": ESTADO_INICIAL},
                ).single()
                return fila is not None

    def jugadores_partido(self, codigo: str) -> list[dict[str, Any]]:
        """Simulación: los planteles de las dos selecciones del partido (relación PERTENECE_A)."""
        with operacion(DEPENDENCIA, "partido.jugadores", _traducir):
            with self._driver.session(
                database=self._database, default_access_mode=READ_ACCESS
            ) as sesion:
                return [r.data() for r in sesion.run(Query(CYPHER_JUGADORES_PARTIDO, timeout=self._timeout),
                                                     {"codigo": codigo})]

    def registrar_evento(self, codigo: str, evento: dict[str, Any]) -> None:
        with operacion(DEPENDENCIA, "evento.crear", _traducir):
            with self._driver.session(
                database=self._database, default_access_mode=WRITE_ACCESS
            ) as sesion:
                sesion.run(Query(CYPHER_REGISTRAR_EVENTO, timeout=self._timeout), {"codigo": codigo, **evento}).consume()

    def ping(self) -> None:
        self._una_fila("ping", "RETURN 1 AS ok", {})

    def cerrar(self) -> None:
        self._driver.close()

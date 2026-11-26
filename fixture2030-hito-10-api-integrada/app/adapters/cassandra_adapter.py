"""Adaptador tabular: Cassandra (Hito 6, keyspace `fixture2030`).

Respeta el modelo del hito de comentarios:
  * lectura del muro sobre `comentarios_por_partido`, siempre con la clave de
    partición completa (id_partido, ventana, shard). Una ventana de 1 minuto
    tiene 4 shards, así que se leen 4 particiones en paralelo y se combinan;
    nunca se usa ALLOW FILTERING ni un escaneo del partido;
Las sentencias son preparadas (parametrizadas) y se crean una sola vez.
"""

import threading
import uuid
import zlib
from datetime import UTC, datetime
from typing import Any

from cassandra import OperationTimedOut, ReadTimeout, Unavailable, WriteTimeout
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable, Session
from cassandra.policies import DCAwareRoundRobinPolicy
from cassandra.query import BatchStatement, BatchType, dict_factory
from cassandra.util import uuid_from_time

from app.adapters.base import no_disponible, operacion, timeout
from app.config.settings import Settings
from app.core.errores import ErrorAPI

DEPENDENCIA = "cassandra"
SHARDS = 4  # mismo valor que fija el productor del Hito 6: crc32(id_usuario) % 4

COLUMNAS_MURO = (
    "id_comentario, id_usuario, usuario_alias, equipo_apoyado, texto, idioma, "
    "estado_moderacion, minuto_partido, creado_en"
)
CQL_MURO = (
    f"SELECT {COLUMNAS_MURO} FROM comentarios_por_partido "
    "WHERE id_partido = ? AND ventana = ? AND shard = ? LIMIT ?"
)
CQL_MURO_CURSOR = (
    f"SELECT {COLUMNAS_MURO} FROM comentarios_por_partido "
    "WHERE id_partido = ? AND ventana = ? AND shard = ? AND id_comentario < ? LIMIT ?"
)
# Portal: escritura doble del Hito 6 (muro por partido + historial por usuario) en un batch LOGGED.
CQL_INSERT_MURO = (
    "INSERT INTO comentarios_por_partido (id_partido, ventana, shard, id_comentario, id_usuario, "
    "usuario_alias, equipo_apoyado, texto, idioma, estado_moderacion, minuto_partido, creado_en) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
CQL_INSERT_USUARIO = (
    "INSERT INTO comentarios_por_usuario (id_usuario, periodo, id_comentario, id_partido, texto, "
    "estado_moderacion, creado_en) VALUES (?, ?, ?, ?, ?, ?, ?)"
)


def shard_de(id_usuario: str) -> int:
    """Mismo criterio que el productor del Hito 6: crc32(id_usuario) % 4."""
    return zlib.crc32(id_usuario.encode("utf-8")) % SHARDS


def _traducir(exc: Exception) -> ErrorAPI | None:
    if isinstance(exc, (OperationTimedOut, ReadTimeout, WriteTimeout)):
        return timeout(DEPENDENCIA)
    if isinstance(exc, (NoHostAvailable, Unavailable, OSError)):
        return no_disponible(DEPENDENCIA)
    return None


def _orden_timeuuid(u: uuid.UUID) -> tuple[int, int, int]:
    # Mismo criterio que el clustering de Cassandra: primero el instante embebido.
    return (u.time, u.clock_seq, u.node)


def _fila(fila: dict[str, Any], codigo_partido: str, ventana: str) -> dict[str, Any]:
    creado = fila["creado_en"]
    if creado is not None and creado.tzinfo is None:
        creado = creado.replace(tzinfo=UTC)
    return {
        "id_comentario": str(fila["id_comentario"]),
        "codigo_partido": codigo_partido,
        "ventana": ventana,
        "id_usuario": fila["id_usuario"],
        "usuario_alias": fila["usuario_alias"],
        "equipo_apoyado": fila["equipo_apoyado"],
        "texto": fila["texto"],
        "idioma": fila["idioma"],
        "estado_moderacion": fila["estado_moderacion"],
        "minuto_partido": fila["minuto_partido"],
        "creado_en": creado,
    }


class CassandraAdapter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._cluster: Cluster | None = None
        self._sesion: Session | None = None
        self._preparadas: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _obtener_sesion(self) -> Session:
        """Conexión perezosa: la API arranca aunque Cassandra esté caída y se
        reconecta en la siguiente request cuando vuelve."""
        if self._sesion is not None:
            return self._sesion
        with self._lock:
            if self._sesion is not None:
                return self._sesion
            s = self._settings
            perfil = ExecutionProfile(
                load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=s.cassandra_dc),
                request_timeout=s.timeout_operacion_s,
                row_factory=dict_factory,
            )
            cluster = Cluster(
                contact_points=s.lista_hosts_cassandra(),
                port=s.cassandra_port,
                execution_profiles={EXEC_PROFILE_DEFAULT: perfil},
                protocol_version=5,
                connect_timeout=s.timeout_conexion_s,
                control_connection_timeout=s.timeout_conexion_s,
            )
            try:
                sesion = cluster.connect(s.cassandra_keyspace)
            except Exception:
                cluster.shutdown()
                raise
            self._preparadas = {
                "muro": sesion.prepare(CQL_MURO),
                "muro_cursor": sesion.prepare(CQL_MURO_CURSOR),
                "insert_muro": sesion.prepare(CQL_INSERT_MURO),
                "insert_usuario": sesion.prepare(CQL_INSERT_USUARIO),
            }
            self._cluster, self._sesion = cluster, sesion
            return sesion

    def leer_muro(
        self, codigo_partido: str, ventana: str, limit: int, cursor: uuid.UUID | None
    ) -> tuple[list[dict[str, Any]], bool]:
        """Devuelve hasta `limit` comentarios (más recientes primero) y si hay más."""
        with operacion(DEPENDENCIA, "comentarios_por_partido.select_ventana", _traducir):
            sesion = self._obtener_sesion()
            # Se pide limit + 1 por shard para saber si existe una página siguiente.
            if cursor is None:
                stmt = self._preparadas["muro"]
                params = [(codigo_partido, ventana, shard, limit + 1) for shard in range(SHARDS)]
            else:
                stmt = self._preparadas["muro_cursor"]
                params = [(codigo_partido, ventana, shard, cursor, limit + 1) for shard in range(SHARDS)]
            futuros = [sesion.execute_async(stmt, p) for p in params]
            filas: list[dict[str, Any]] = []
            for futuro in futuros:
                # Si falla un shard falla toda la lectura: no se devuelve un muro parcial.
                filas.extend(futuro.result())
        filas.sort(key=lambda f: _orden_timeuuid(f["id_comentario"]), reverse=True)
        hay_mas = len(filas) > limit
        return [_fila(f, codigo_partido, ventana) for f in filas[:limit]], hay_mas

    # ----------------------------------------------------------------- portal
    def leer_muro_ventanas(self, codigo_partido: str, ventanas: list[str], limit: int) -> list[dict[str, Any]]:
        """Portal: últimos comentarios de varias ventanas (4 particiones por ventana, en paralelo)."""
        with operacion(DEPENDENCIA, "comentarios_por_partido.select_ventanas", _traducir):
            sesion = self._obtener_sesion()
            stmt = self._preparadas["muro"]
            futuros = [
                (v, sesion.execute_async(stmt, (codigo_partido, v, shard, limit)))
                for v in ventanas
                for shard in range(SHARDS)
            ]
            filas = [(v, f) for v, futuro in futuros for f in futuro.result()]
        filas.sort(key=lambda par: _orden_timeuuid(par[1]["id_comentario"]), reverse=True)
        return [_fila(f, codigo_partido, v) for v, f in filas[:limit]]

    def publicar_comentario(self, c: dict[str, Any]) -> dict[str, Any]:
        """Inserta en comentarios_por_partido y comentarios_por_usuario (batch LOGGED)."""
        ahora = datetime.now(UTC)
        id_comentario = uuid_from_time(ahora)
        ventana = ahora.strftime("%Y%m%d%H%M")
        with operacion(DEPENDENCIA, "comentarios.insert", _traducir):
            sesion = self._obtener_sesion()
            batch = BatchStatement(batch_type=BatchType.LOGGED)
            batch.add(self._preparadas["insert_muro"], (
                c["codigo_partido"], ventana, shard_de(c["id_usuario"]), id_comentario, c["id_usuario"],
                c["usuario_alias"], c["equipo_apoyado"], c["texto"], "es", "publicado", c["minuto_partido"], ahora,
            ))
            batch.add(self._preparadas["insert_usuario"], (
                c["id_usuario"], ahora.strftime("%Y%m"), id_comentario, c["codigo_partido"], c["texto"],
                "publicado", ahora,
            ))
            sesion.execute(batch)
        return {
            **c, "id_comentario": str(id_comentario), "ventana": ventana, "idioma": "es",
            "estado_moderacion": "publicado", "creado_en": ahora,
        }

    def ping(self) -> None:
        with operacion(DEPENDENCIA, "ping", _traducir):
            self._obtener_sesion().execute("SELECT release_version FROM system.local")

    def cerrar(self) -> None:
        if self._cluster is not None:
            self._cluster.shutdown()

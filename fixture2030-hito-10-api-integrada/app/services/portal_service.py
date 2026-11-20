"""Portal del Fixture 2030: navegación e interacción sobre las bases del TPO.

Combina lecturas (Neo4j: fixture; MongoDB: selecciones y planteles) con escrituras
acotadas de demostración (Redis: sesiones, visitas, conectados y encuesta; Cassandra:
comentarios del muro). Las escrituras exigen una sesión vigente en Redis.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.errores import Conflicto, ErrorValidacion, RecursoNoEncontrado, SesionNoVigente, SesionRequerida
from app.schemas.portal import (
    EstadoVivo,
    MuroPortal,
    NuevaSesion,
    NuevoComentario,
    PartidoFixture,
    Plantel,
    SesionPortal,
)
from app.schemas.equipos import EquipoDetalle


class PortalService:
    def __init__(self, mongodb: Any, neo4j: Any, cassandra: Any, redis: Any,
                 ttl_sesion_s: int = 1800, ventanas_muro: int = 15):
        self._mongo, self._neo4j, self._cassandra, self._redis = mongodb, neo4j, cassandra, redis
        self._ttl_sesion_s = ttl_sesion_s
        self._ventanas_muro = ventanas_muro

    # ------------------------------------------------------------- navegación
    def partidos(self) -> list[PartidoFixture]:
        return [PartidoFixture(**p) for p in self._neo4j.listar_partidos()]

    def equipos(self) -> list[EquipoDetalle]:
        return [EquipoDetalle(**e) for e in self._mongo.listar_equipos()]

    def plantel(self, codigo_iso: str) -> Plantel:
        equipo = self._mongo.obtener_equipo(codigo_iso)
        if equipo is None:
            raise RecursoNoEncontrado(f"No existe la selección '{codigo_iso}'.")
        return Plantel(equipo=EquipoDetalle(**equipo), jugadores=self._mongo.jugadores_equipo(codigo_iso))

    def _partido(self, codigo: str) -> PartidoFixture:
        for p in self.partidos():
            if p.codigo_partido == codigo:
                return p
        raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")

    # ---------------------------------------------------------------- sesiones
    def iniciar_sesion(self, datos: NuevaSesion) -> SesionPortal:
        creada = self._redis.crear_sesion(datos.alias.strip(), datos.equipo_favorito, self._ttl_sesion_s)
        return self.sesion(creada["id_sesion"])

    def sesion(self, id_sesion: str) -> SesionPortal:
        datos = self._redis.leer_sesion_portal(id_sesion)
        if datos is None:
            raise SesionNoVigente(f"No existe una sesión vigente con id '{id_sesion}'.")
        return SesionPortal(**datos)

    def cerrar_sesion(self, id_sesion: str) -> None:
        self._redis.cerrar_sesion(id_sesion)

    def _usuario(self, id_sesion: str | None) -> SesionPortal:
        datos = self._redis.leer_sesion_portal(id_sesion) if id_sesion else None
        if datos is None:
            raise SesionRequerida("Iniciá sesión para realizar esta acción (sesión inexistente o vencida).")
        return SesionPortal(**datos)

    # ------------------------------------------------------------------- muro
    def muro(self, codigo: str, limit: int) -> MuroPortal:
        ahora = datetime.now(UTC)
        ventanas = [(ahora - timedelta(minutes=i)).strftime("%Y%m%d%H%M") for i in range(self._ventanas_muro)]
        items = self._cassandra.leer_muro_ventanas(codigo, ventanas, limit)
        return MuroPortal(codigo_partido=codigo, ventanas=ventanas, items=items)

    def comentar(self, codigo: str, id_sesion: str | None, datos: NuevoComentario) -> dict[str, Any]:
        usuario = self._usuario(id_sesion)
        partido = self._partido(codigo)
        equipos = {e.codigo_iso for e in partido.equipos}
        if datos.equipo_apoyado not in equipos:
            raise ErrorValidacion(
                "El equipo apoyado no juega este partido.",
                [{"campo": "body.equipo_apoyado", "mensaje": " o ".join(sorted(equipos))}],
            )
        return self._cassandra.publicar_comentario({
            "codigo_partido": codigo,
            "id_usuario": usuario.usuario_id,
            "usuario_alias": usuario.alias,
            "equipo_apoyado": datos.equipo_apoyado,
            "texto": datos.texto.strip(),
            "minuto_partido": datos.minuto_partido,
        })

    # --------------------------------------------------------------- en vivo
    def _vivo(self, codigo: str, usuario_id: str | None) -> EstadoVivo:
        return EstadoVivo(codigo_partido=codigo, **self._redis.estado_vivo(codigo, usuario_id))

    def _usuario_opcional(self, id_sesion: str | None) -> SesionPortal | None:
        datos = self._redis.leer_sesion_portal(id_sesion) if id_sesion else None
        return SesionPortal(**datos) if datos else None

    def vivo(self, codigo: str, id_sesion: str | None) -> EstadoVivo:
        usuario = self._usuario_opcional(id_sesion)
        return self._vivo(codigo, usuario.usuario_id if usuario else None)

    def visita(self, codigo: str, id_sesion: str | None) -> EstadoVivo:
        self._partido(codigo)
        usuario = self._usuario_opcional(id_sesion)
        self._redis.registrar_visita(codigo, usuario.usuario_id if usuario else None, id_sesion if usuario else None)
        return self._vivo(codigo, usuario.usuario_id if usuario else None)

    def votar(self, codigo: str, id_sesion: str | None, id_jugador: str) -> EstadoVivo:
        usuario = self._usuario(id_sesion)
        partido = self._partido(codigo)
        if id_jugador.split("-")[0] not in {e.codigo_iso for e in partido.equipos}:
            raise ErrorValidacion(
                "El jugador no pertenece a ninguna de las selecciones del partido.",
                [{"campo": "body.id_jugador", "mensaje": id_jugador}],
            )
        if not self._redis.votar_figura(codigo, usuario.usuario_id, id_jugador):
            raise Conflicto("Ya votaste la figura de este partido.")
        return self._vivo(codigo, usuario.usuario_id)

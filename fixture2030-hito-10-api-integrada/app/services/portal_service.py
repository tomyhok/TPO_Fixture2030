"""Portal del Fixture 2030: navegación e interacción sobre las bases del TPO.

Combina lecturas (Neo4j: fixture; MongoDB: selecciones y planteles) con escrituras
acotadas de demostración (Redis: sesiones, visitas, conectados y reloj; Cassandra:
comentarios del muro). Las escrituras exigen una sesión vigente en Redis. El prode
(predicciones, puntajes y tabla de posiciones en MongoDB) está en prode_service.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.errores import Conflicto, ErrorValidacion, RecursoNoEncontrado, SesionNoVigente, SesionRequerida
from app.schemas.portal import (
    ORDEN_ESTADOS,
    EstadoPartido,
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
                 ttl_sesion_s: int = 1800, ventanas_muro: int = 15, simulador: Any = None):
        self._mongo, self._neo4j, self._cassandra, self._redis = mongodb, neo4j, cassandra, redis
        self._simulador = simulador
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

    def partido(self, codigo: str) -> PartidoFixture:
        for p in self.partidos():
            if p.codigo_partido == codigo:
                return p
        raise RecursoNoEncontrado(f"No existe el partido '{codigo}'.")

    def cambiar_estado(self, codigo: str, id_sesion: str | None, nuevo: EstadoPartido) -> PartidoFixture:
        """Control de la demo: avanza el estado del partido en Neo4j. Solo hacia adelante,
        así un partido finalizado (y puntuado en el prode) no vuelve a abrirse.
        Iniciar un partido programado arranca la simulación en tiempo real (simulador_service);
        finalizarlo a mano la detiene."""
        self.usuario(id_sesion)
        partido = self.partido(codigo)
        actual = partido.estado
        if ORDEN_ESTADOS.index(nuevo) <= ORDEN_ESTADOS.index(actual):
            raise Conflicto(f"El partido {codigo} está '{actual}': solo puede avanzar "
                            f"({' -> '.join(e.value for e in ORDEN_ESTADOS)}).")
        simular = (self._simulador is not None and actual == EstadoPartido.programado
                   and nuevo == EstadoPartido.en_juego)
        jugadores = self._simulador.preparar(codigo) if simular else None
        inicio = datetime.now(UTC).replace(microsecond=0) if simular else None
        if not self._neo4j.cambiar_estado(codigo, actual.value, nuevo.value,
                                          inicio.strftime("%Y-%m-%dT%H:%M:%SZ") if inicio else None):
            raise Conflicto(f"El estado de {codigo} cambió mientras tanto; volvé a cargar el partido.")
        if simular:
            self._simulador.iniciar(partido, jugadores, inicio)
        elif nuevo == EstadoPartido.finalizado and self._simulador is not None:
            self._simulador.detener(codigo)
        return self.partido(codigo)

    # ---------------------------------------------------------------- sesiones
    def iniciar_sesion(self, datos: NuevaSesion) -> SesionPortal:
        """La sesión vive en Redis; la identidad, en MongoDB (usuarios_portal). Volver a
        ingresar con el mismo alias recupera el mismo usuario_id, y con él sus predicciones
        y su puesto en la tabla. Es una demo sin contraseña: el alias identifica al usuario."""
        alias = datos.alias.strip()
        creada = self._redis.crear_sesion(alias, datos.equipo_favorito, self._ttl_sesion_s)
        usuario_id = self._mongo.registrar_usuario_portal(alias, creada["usuario_id"], datos.equipo_favorito)
        if usuario_id != creada["usuario_id"]:
            self._redis.asignar_usuario_sesion(creada["id_sesion"], usuario_id)
        return self.sesion(creada["id_sesion"])

    def sesion(self, id_sesion: str) -> SesionPortal:
        datos = self._redis.leer_sesion_portal(id_sesion)
        if datos is None:
            raise SesionNoVigente(f"No existe una sesión vigente con id '{id_sesion}'.")
        return SesionPortal(**datos)

    def cerrar_sesion(self, id_sesion: str) -> None:
        self._redis.cerrar_sesion(id_sesion)

    def usuario(self, id_sesion: str | None) -> SesionPortal:
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
        usuario = self.usuario(id_sesion)
        partido = self.partido(codigo)
        equipos = {e.codigo_iso for e in partido.equipos}
        if datos.equipo_apoyado not in equipos:
            raise ErrorValidacion(
                "El equipo apoyado no juega este partido.",
                [{"campo": "body.equipo_apoyado", "mensaje": " o ".join(sorted(equipos))}],
            )
        # El minuto no lo elige el usuario: es el del reloj de la simulación en Redis, si el
        # partido se está jugando; si no, el comentario queda sin minuto.
        reloj = self._redis.leer_reloj(codigo)
        minuto = reloj["minuto"] if reloj and reloj["en_curso"] else None
        return self._cassandra.publicar_comentario({
            "codigo_partido": codigo,
            "id_usuario": usuario.usuario_id,
            "usuario_alias": usuario.alias,
            "equipo_apoyado": datos.equipo_apoyado,
            "texto": datos.texto.strip(),
            "minuto_partido": minuto,
        })

    # --------------------------------------------------------------- en vivo
    def _vivo(self, codigo: str, usuario_id: str | None) -> EstadoVivo:
        return EstadoVivo(codigo_partido=codigo, **self._redis.estado_vivo(codigo, usuario_id))

    def usuario_opcional(self, id_sesion: str | None) -> SesionPortal | None:
        datos = self._redis.leer_sesion_portal(id_sesion) if id_sesion else None
        return SesionPortal(**datos) if datos else None

    def vivo(self, codigo: str, id_sesion: str | None) -> EstadoVivo:
        usuario = self.usuario_opcional(id_sesion)
        return self._vivo(codigo, usuario.usuario_id if usuario else None)

    def visita(self, codigo: str, id_sesion: str | None) -> EstadoVivo:
        self.partido(codigo)
        usuario = self.usuario_opcional(id_sesion)
        self._redis.registrar_visita(codigo, usuario.usuario_id if usuario else None, id_sesion if usuario else None)
        return self._vivo(codigo, usuario.usuario_id if usuario else None)

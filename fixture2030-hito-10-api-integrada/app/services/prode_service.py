"""Prode del portal: predicciones de resultados, puntajes y tabla de posiciones.

Todo se guarda en MongoDB. Neo4j se lee para aplicar las reglas: que el partido exista,
quién es local y visitante, su estado y los goles (eventos `Gol`). Redis aporta la sesión
vigente del usuario que pronostica. Se puede pronosticar mientras el partido está
'Programado'; cuando pasa a 'Finalizado' se puntúa.

La puntuación es perezosa e idempotente: al pedir la tabla, "mis predicciones" o el
resumen de un partido se liquidan los partidos ya finalizados que tengan predicciones
pendientes. No hace falta un proceso aparte.
"""

from typing import Any

from app.core.errores import ErrorDependencia, PrediccionCerrada
from app.core.observabilidad import logger
from app.schemas.portal import EstadoPartido, PartidoFixture
from app.schemas.prode import NuevaPrediccion, Prediccion, ResumenPredicciones, TablaPosiciones
from app.services.portal_service import PortalService

PUNTOS_EXACTO = 3     # acertar el marcador exacto
PUNTOS_RESULTADO = 1  # acertar solo quién gana o el empate
ESTADO_ABIERTO = EstadoPartido.programado
ESTADO_FINALIZADO = EstadoPartido.finalizado

_log = logger("servicio.prode")


def local_visitante(partido: PartidoFixture) -> tuple[str, str]:
    por_condicion = {e.condicion: e.codigo_iso for e in partido.equipos}
    if "local" in por_condicion and "visitante" in por_condicion:
        return por_condicion["local"], por_condicion["visitante"]
    codigos = [e.codigo_iso for e in partido.equipos]
    return codigos[0], codigos[1]


def marcador(eventos: list[dict[str, Any]], local: str, visitante: str) -> tuple[int, int]:
    """Mismo criterio que el marcador del portal: cada evento `Gol*` con protagonista suma
    para la selección del jugador (prefijo de id_jugador, p. ej. ARG-10 → ARG)."""
    goles = {local: 0, visitante: 0}
    for ev in eventos:
        if str(ev.get("tipo", "")).lower().startswith("gol") and ev.get("jugador"):
            iso = ev["jugador"]["id_jugador"].split("-")[0]
            if iso in goles:
                goles[iso] += 1
    return goles[local], goles[visitante]


class ProdeService:
    def __init__(self, portal: PortalService, mongodb: Any, neo4j: Any):
        self._portal, self._mongo, self._neo4j = portal, mongodb, neo4j

    # ------------------------------------------------------------- pronosticar
    def pronosticar(self, codigo: str, id_sesion: str | None, datos: NuevaPrediccion) -> Prediccion:
        usuario = self._portal.usuario(id_sesion)
        partido = self._portal.partido(codigo)
        if partido.estado != ESTADO_ABIERTO:
            raise PrediccionCerrada(f"Los pronósticos de {codigo} cerraron: el partido está '{partido.estado}'.")
        local, visitante = local_visitante(partido)
        doc = self._mongo.guardar_prediccion({
            "codigo_partido": codigo,
            "usuario_id": usuario.usuario_id,
            "fase": partido.fase,
            "equipo_local": local,
            "equipo_visitante": visitante,
            "goles_local": datos.goles_local,
            "goles_visitante": datos.goles_visitante,
        })
        if doc is None:
            raise PrediccionCerrada(f"Tu pronóstico de {codigo} ya fue puntuado y no se puede cambiar.")
        return Prediccion(**doc)

    # ---------------------------------------------------------------- lecturas
    def resumen(self, codigo: str, id_sesion: str | None) -> ResumenPredicciones:
        partido = self._portal.partido(codigo)
        if partido.estado == ESTADO_FINALIZADO and codigo in self._mongo.partidos_pendientes():
            self._liquidar(partido)
        usuario = self._portal.usuario_opcional(id_sesion)
        r = self._mongo.resumen_predicciones(codigo, usuario.usuario_id if usuario else None)
        abierta = partido.estado == ESTADO_ABIERTO and r["resultado_real"] is None
        return ResumenPredicciones(codigo_partido=codigo, estado=partido.estado, abierta=abierta, **r)

    def mias(self, id_sesion: str | None) -> list[Prediccion]:
        usuario = self._portal.usuario(id_sesion)
        self.liquidar_pendientes()
        return [Prediccion(**p) for p in self._mongo.predicciones_usuario(usuario.usuario_id)]

    def posiciones(self, id_sesion: str | None, equipo: str | None, limit: int) -> TablaPosiciones:
        pendientes = self.liquidar_pendientes()
        usuario = self._portal.usuario_opcional(id_sesion)
        t = self._mongo.tabla_posiciones(equipo, limit, usuario.usuario_id if usuario else None)
        return TablaPosiciones(equipo=equipo, puntos_exacto=PUNTOS_EXACTO, puntos_resultado=PUNTOS_RESULTADO,
                               pendientes=pendientes, **t)

    # --------------------------------------------------------------- puntuación
    def liquidar_pendientes(self) -> list[str]:
        """Puntúa los partidos finalizados con predicciones pendientes. Si Neo4j no responde,
        esos partidos quedan para la próxima consulta y la tabla se sirve igual.
        Devuelve los partidos que no se pudieron verificar."""
        pendientes = self._mongo.partidos_pendientes()
        if not pendientes:
            return []
        sin_verificar: list[str] = []
        try:
            partidos = {p.codigo_partido: p for p in self._portal.partidos()}
        except ErrorDependencia as error:
            _log.warning("liquidacion_postergada partidos=%s dependencia=%s", pendientes, error.dependencia)
            return pendientes
        for codigo in pendientes:
            partido = partidos.get(codigo)
            if partido is None or partido.estado != ESTADO_FINALIZADO:
                continue
            try:
                self._liquidar(partido)
            except ErrorDependencia as error:
                _log.warning("liquidacion_postergada partido=%s dependencia=%s", codigo, error.dependencia)
                sin_verificar.append(codigo)
        return sin_verificar

    def _liquidar(self, partido: PartidoFixture) -> None:
        codigo = partido.codigo_partido
        local, visitante = local_visitante(partido)
        datos = self._neo4j.eventos_partido(codigo, 200) or {"eventos": []}
        gl, gv = marcador(datos["eventos"], local, visitante)
        n = self._mongo.liquidar_partido(codigo, gl, gv, PUNTOS_EXACTO, PUNTOS_RESULTADO)
        if n:
            _log.info("partido_liquidado partido=%s marcador=%d-%d predicciones=%d", codigo, gl, gv, n)

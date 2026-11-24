"""Simulación de un partido en tiempo real para la demo del portal.

Al iniciar un partido programado desde el portal, un hilo recorre los 90 minutos (más el
descuento) en `simulacion_duracion_s` segundos reales (60 por defecto) y escribe en las
bases como lo haría el sistema durante un partido real:

  * Neo4j: goles y tarjetas como (Jugador)-[:PROTAGONIZA]->(Evento)-[:CORRESPONDE_A]->(Partido)
    y, al final, el estado 'Finalizado' (con eso el prode puntúa el partido).
  * InfluxDB: un punto por minuto y selección en `estadisticas_partido` (posesión, pases, tiros,
    hinchas conectados). La marca de tiempo es `inicio + minuto de juego`, así el gráfico queda
    en minutos de partido aunque la simulación dure un minuto real.
  * Cassandra: los mensajes del relator en el muro (inicio, goles, expulsiones, entretiempo, final)
    y los comentarios de una hinchada simulada: charlas durante el partido según quién domina,
    reacciones a goles y expulsiones, entretiempo y final. Cada comentario es la misma doble
    escritura del portal (comentarios_por_partido + comentarios_por_usuario).
  * Redis: el reloj `reloj:partido:<p>` que el portal consulta cada segundo.

Si una base falla en medio de la simulación, se registra y se sigue: el partido llega igual
al final. Los eventos llevan `simulado: true` para que `scripts/reiniciar_demo.py` los borre.
"""

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.errores import Conflicto, ErrorAPI
from app.core.observabilidad import logger
from app.schemas.portal import EstadoPartido, PartidoFixture
from app.services.prode_service import local_visitante

MINUTOS = 90
GOLES_POR_PARTIDO = 3.0
AMARILLAS_POR_PARTIDO = 3.5
ROJAS_DIRECTAS_POR_PARTIDO = 0.2
TIROS_POR_MINUTO = 0.14  # por selección, además de los goles
PESO_GOL = {"DEL": 6, "MED": 3, "DEF": 1, "ARQ": 0}
PESO_TARJETA = {"DEF": 4, "MED": 3, "DEL": 1, "ARQ": 0.3}
RELATOR = {"id_usuario": "U-0000", "usuario_alias": "Relator Fixture 2030"}

# Hinchada simulada: cada alias tiene un id fijo (U-9001..), así comentarios_por_usuario junta su
# historial de varios partidos. En cada partido la mitad alienta al local y la otra al visitante.
HINCHAS = [
    "tribuna_norte", "la_doce_siempre", "futbolero_92", "el_profe_tactico", "abuela_futbolera",
    "hincha_de_sofa", "garra_y_corazon", "pibe_del_barrio", "mister_posesion", "cronista_amateur",
    "la_banda_del_bombo", "mate_y_futbol", "pasion_mundialista", "el_9_de_area", "doble_cinco",
    "contragolpe", "vuelta_olimpica", "arquero_volador", "tiki_taka", "palco_vip",
    "remera_de_la_suerte", "grito_sagrado", "camiseta_10", "fan_del_var",
]
CHARLA_POR_MINUTO = 0.8  # probabilidad de un comentario suelto en cada minuto de juego
# Plantillas: {eq} propia selección, {rival}, {jugador}, {marcador} (propio-rival), {sede}, {min}.
FRASES = {
    "charla": [
        "¡Vamos {eq}!", "Hoy se gana, lo siento en el pecho", "Tranquilos, hay que tener la pelota",
        "Qué ambiente hay en el {sede}", "Falta juego por las bandas", "Presionen arriba que se equivocan",
        "Desde casa alentando a {eq} 🙌", "Con este equipo vamos lejos", "{min} y seguimos firmes",
        "¡Esa defensa!", "Partidazo para mirar con mate", "Cuidado con las contras de {rival}",
    ],
    "domina": [
        "Somos dueños de la pelota, falta el último pase", "{rival} no la toca hace rato",
        "Así se juega, a lo {eq}", "Ya va a llegar el gol, estamos encima",
    ],
    "sufre": [
        "No pasamos de mitad de cancha...", "Hay que adelantar las líneas", "{rival} nos tiene arrinconados",
        "Aguantemos, ya va a cambiar",
    ],
    "descuento": ["¡Cuánto falta, árbitro!", "Aguantá, aguantá...", "¡Último ataque, vamos {eq}!"],
    "gol_a_favor": [
        "¡GOOOOL! ¡{jugador}! 🔥", "¡Qué golazo de {jugador}!", "¡Lo grité como loco! {marcador}",
        "¡Vamos {eq}, vamos!", "{jugador} es enorme", "¡Golazo! Se lo merecía el equipo",
    ],
    "gol_en_contra": [
        "No puede ser... ¿quién marcaba a {jugador}?", "Hay tiempo, ¡vamos que se da vuelta!",
        "Despertate, defensa", "Uff, qué bronca", "Tranquilos, todavía queda partido",
    ],
    "roja_rival": ["¡Bien echado!", "Ahora a aprovechar el hombre de más", "Roja clarísima"],
    "roja_propia": ["¡Exagerado el árbitro!", "Nos dejan con diez, a aguantar", "Que revise el VAR eso"],
    "entretiempo_gana": ["Buen primer tiempo, a sostenerlo", "Así, con esta actitud. {marcador}"],
    "entretiempo_empata": ["Parejo, se define en el segundo tiempo", "Falta un poco más de profundidad"],
    "entretiempo_pierde": ["Hay que cambiar algo en el segundo tiempo", "Se puede dar vuelta, vamos {eq}"],
    "final_gana": ["¡GANAMOS! 🎉 {marcador}", "Tres puntos de oro", "¡Qué partido! Orgulloso de {eq}"],
    "final_empata": ["Un punto que sirve", "Empate justo, a ganar el próximo"],
    "final_pierde": ["Duele, pero el grupo sigue abierto", "Hoy no fue... a levantar cabeza", "{rival} fue mejor, hay que reconocerlo"],
}
TTL_LATIDO_S = 15  # mientras corre: si la API se cae, el reloj vence solo
TTL_FINAL_S = 3 * 3600

_log = logger("servicio.simulador")


def formato_minuto(minuto: int) -> str:
    return f"90+{minuto - MINUTOS}'" if minuto > MINUTOS else f"{minuto}'"


@dataclass
class _Partido:
    codigo: str
    local: str
    visitante: str
    nombres: dict[str, str]
    plantel: dict[str, list[dict[str, Any]]]
    sede: str | None
    inicio: datetime
    rnd: random.Random
    goles: dict[str, int] = field(default_factory=dict)
    pases: dict[str, int] = field(default_factory=dict)
    tiros: dict[str, int] = field(default_factory=dict)
    usuarios: dict[str, int] = field(default_factory=dict)
    posesion_local: float = 50.0
    amarillas: set[str] = field(default_factory=set)
    expulsados: set[str] = field(default_factory=set)
    eventos: int = 0
    hinchas: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # selección -> (id, alias)

    def marcador(self) -> str:
        return (f"{self.nombres[self.local]} {self.goles[self.local]} - "
                f"{self.goles[self.visitante]} {self.nombres[self.visitante]}")


class SimuladorService:
    def __init__(self, neo4j: Any, influx: Any, cassandra: Any, redis: Any, duracion_s: float = 60.0,
                 semilla: int | None = None):
        self._neo4j, self._influx, self._cassandra, self._redis = neo4j, influx, cassandra, redis
        self._duracion_s = duracion_s
        self._semilla = semilla  # fija solo en las pruebas
        self._hilos: dict[str, tuple[threading.Thread, threading.Event]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ ciclo de vida
    def preparar(self, codigo: str) -> list[dict[str, Any]]:
        """Se llama antes de cambiar el estado: si Neo4j no responde o faltan planteles,
        el partido no arranca (queda 'Programado')."""
        jugadores = self._neo4j.jugadores_partido(codigo)
        if len({j["codigo_iso"] for j in jugadores}) < 2:
            raise Conflicto(f"No se puede simular {codigo}: faltan los planteles en Neo4j.")
        return jugadores

    def iniciar(self, partido: PartidoFixture, jugadores: list[dict[str, Any]], inicio: datetime) -> None:
        local, visitante = local_visitante(partido)
        plantel: dict[str, list[dict[str, Any]]] = {local: [], visitante: []}
        for j in jugadores:
            plantel.setdefault(j["codigo_iso"], []).append(j)
        p = _Partido(
            codigo=partido.codigo_partido, local=local, visitante=visitante,
            nombres={e.codigo_iso: e.nombre or e.codigo_iso for e in partido.equipos},
            plantel=plantel, sede=partido.sede.nombre if partido.sede else None, inicio=inicio,
            rnd=random.Random(self._semilla),
        )
        parar = threading.Event()
        hilo = threading.Thread(target=self._correr, args=(p, parar), name=f"simulacion-{p.codigo}", daemon=True)
        with self._lock:
            self._hilos[p.codigo] = (hilo, parar)
        hilo.start()
        _log.info("simulacion_iniciada partido=%s duracion_s=%.0f", p.codigo, self._duracion_s)

    def detener(self, codigo: str) -> None:
        with self._lock:
            activo = self._hilos.get(codigo)
        if activo:
            activo[1].set()

    def en_curso(self, codigo: str) -> bool:
        with self._lock:
            activo = self._hilos.get(codigo)
        return bool(activo and activo[0].is_alive())

    def esperar(self, codigo: str, timeout: float) -> bool:
        """Pruebas: espera a que termine la simulación. True si terminó."""
        with self._lock:
            activo = self._hilos.get(codigo)
        if activo:
            activo[0].join(timeout)
            return not activo[0].is_alive()
        return True

    def cerrar(self) -> None:
        with self._lock:
            activos = list(self._hilos.values())
        for _, parar in activos:
            parar.set()
        for hilo, _ in activos:
            hilo.join(2)

    # --------------------------------------------------------------- simulación
    def _correr(self, p: _Partido, parar: threading.Event) -> None:
        try:
            self._jugar(p, parar)
        except Exception:  # noqa: BLE001 - el hilo no debe morir en silencio
            _log.exception("simulacion_interrumpida partido=%s", p.codigo)
            self._paso("reloj", lambda: self._redis.actualizar_reloj(p.codigo, 0, 0, False, TTL_FINAL_S))
        finally:
            with self._lock:
                self._hilos.pop(p.codigo, None)

    def _jugar(self, p: _Partido, parar: threading.Event) -> None:
        rnd = p.rnd
        for eq, (minimo, maximo) in ((p.local, (150_000, 300_000)), (p.visitante, (80_000, 200_000))):
            p.goles[eq], p.pases[eq], p.tiros[eq] = 0, 0, 0
            p.usuarios[eq] = rnd.randint(minimo, maximo)
        orden = list(range(len(HINCHAS)))
        rnd.shuffle(orden)
        mitad = len(orden) // 2
        p.hinchas = {eq: [(f"U-{9001 + i}", HINCHAS[i]) for i in indices]
                     for eq, indices in ((p.local, orden[:mitad]), (p.visitante, orden[mitad:]))}
        adicion = rnd.randint(1, 5)
        total = MINUTOS + adicion
        paso_s = self._duracion_s / total
        t0 = time.monotonic()

        self._reloj(p, 0, adicion, True)
        self._estadisticas(p, 0)
        self._relatar(p, None, 0, f"¡Arranca el partido! {p.nombres[p.local]} vs {p.nombres[p.visitante]}"
                                     + (f" en el {p.sede}." if p.sede else "."))
        for minuto in range(1, total + 1):
            if parar.wait(max(0.0, t0 + minuto * paso_s - time.monotonic())):
                # Lo finalizaron a mano desde el portal o se está apagando la API.
                self._reloj(p, minuto - 1, adicion, False)
                _log.info("simulacion_detenida partido=%s minuto=%d", p.codigo, minuto - 1)
                return
            self._jugar_minuto(p, minuto)
            self._estadisticas(p, minuto)
            self._reloj(p, minuto, adicion, True)
            if minuto == 45:
                self._relatar(p, None, 45, f"Final del primer tiempo: {p.marcador()}.")
                for eq in (p.local, p.visitante):
                    self._hincha(p, eq, 45, f"entretiempo_{self._situacion(p, eq)}")

        # Primero el estado en Neo4j y después el reloj: cuando el portal ve el reloj
        # detenido, vuelve a cargar el partido y ya lo encuentra finalizado.
        self._paso("estado", lambda: self._neo4j.cambiar_estado(
            p.codigo, EstadoPartido.en_juego.value, EstadoPartido.finalizado.value))
        self._relatar(p, None, total, f"¡Terminó el partido! {p.marcador()}.")
        for eq in (p.local, p.visitante):
            for _ in range(2):
                self._hincha(p, eq, total, f"final_{self._situacion(p, eq)}")
        self._reloj(p, total, adicion, False)
        _log.info("simulacion_finalizada partido=%s marcador=%s", p.codigo, p.marcador())

    def _jugar_minuto(self, p: _Partido, minuto: int) -> None:
        rnd = p.rnd
        p.posesion_local = max(30.0, min(70.0, p.posesion_local + rnd.uniform(-4, 4)))
        posesion = {p.local: p.posesion_local, p.visitante: 100 - p.posesion_local}
        for eq in (p.local, p.visitante):
            p.pases[eq] += round(rnd.uniform(3, 7) * posesion[eq] / 50)
            p.usuarios[eq] = max(1_000, p.usuarios[eq] + rnd.randint(-1_500, 2_500))
            if rnd.random() < TIROS_POR_MINUTO:
                p.tiros[eq] += 1

        if rnd.random() < GOLES_POR_PARTIDO / MINUTOS:
            eq = p.local if rnd.random() < posesion[p.local] / 100 else p.visitante
            jugador = self._elegir(p, eq, PESO_GOL)
            if jugador:
                p.goles[eq] += 1
                p.tiros[eq] += 1
                p.usuarios = {e: int(u * 1.15) for e, u in p.usuarios.items()}
                self._evento(p, "Gol", minuto, jugador)
                self._relatar(p, eq, minuto, f"⚽ ¡GOOOL de {p.nombres[eq]}! {jugador['nombre']} "
                                             f"a los {formato_minuto(minuto)}. {p.marcador()}.")
                rival = self._rival(p, eq)
                for _ in range(rnd.randint(2, 3)):
                    self._hincha(p, eq, minuto, "gol_a_favor", jugador["nombre"])
                for _ in range(rnd.randint(1, 2)):
                    self._hincha(p, rival, minuto, "gol_en_contra", jugador["nombre"])

        if rnd.random() < AMARILLAS_POR_PARTIDO / MINUTOS:
            eq = rnd.choice((p.local, p.visitante))
            jugador = self._elegir(p, eq, PESO_TARJETA)
            if jugador and jugador["id_jugador"] in p.amarillas:
                self._expulsar(p, eq, minuto, jugador, "doble amarilla")
            elif jugador:
                p.amarillas.add(jugador["id_jugador"])
                self._evento(p, "Tarjeta Amarilla", minuto, jugador)
        elif rnd.random() < ROJAS_DIRECTAS_POR_PARTIDO / MINUTOS:
            eq = rnd.choice((p.local, p.visitante))
            jugador = self._elegir(p, eq, PESO_TARJETA)
            if jugador:
                self._expulsar(p, eq, minuto, jugador, "roja directa")

        # Charla de la tribuna: el tono depende de quién tiene la pelota (y del descuento).
        if rnd.random() < CHARLA_POR_MINUTO:
            eq = rnd.choice((p.local, p.visitante))
            if minuto > MINUTOS:
                tipo = "descuento"
            elif posesion[eq] > 58:
                tipo = "domina"
            elif posesion[eq] < 42:
                tipo = "sufre"
            else:
                tipo = "charla"
            self._hincha(p, eq, minuto, tipo)

    def _expulsar(self, p: _Partido, eq: str, minuto: int, jugador: dict[str, Any], motivo: str) -> None:
        p.expulsados.add(jugador["id_jugador"])
        self._evento(p, "Tarjeta Roja", minuto, jugador)
        self._relatar(p, eq, minuto, f"🟥 Expulsado {jugador['nombre']} ({p.nombres[eq]}) por {motivo} "
                                     f"a los {formato_minuto(minuto)}.")
        self._hincha(p, eq, minuto, "roja_propia", jugador["nombre"])
        self._hincha(p, self._rival(p, eq), minuto, "roja_rival", jugador["nombre"])

    @staticmethod
    def _rival(p: _Partido, eq: str) -> str:
        return p.visitante if eq == p.local else p.local

    def _situacion(self, p: _Partido, eq: str) -> str:
        propios, ajenos = p.goles[eq], p.goles[self._rival(p, eq)]
        return "gana" if propios > ajenos else "pierde" if propios < ajenos else "empata"

    @staticmethod
    def _elegir(p: _Partido, eq: str, pesos: dict[str, float]) -> dict[str, Any] | None:
        candidatos = [j for j in p.plantel.get(eq, []) if j["id_jugador"] not in p.expulsados
                      and pesos.get(j.get("posicion") or "", 1) > 0]
        if not candidatos:
            return None
        return p.rnd.choices(candidatos, weights=[pesos.get(j.get("posicion") or "", 1) for j in candidatos])[0]

    # ---------------------------------------------------------- escrituras
    def _paso(self, que: str, fn: Any) -> Any:
        try:
            return fn()
        except ErrorAPI as error:
            # La base no respondió: la simulación sigue (lo mismo pasaría con un partido real).
            _log.warning("simulacion_paso_fallido que=%s codigo=%s", que, error.codigo)
        except Exception:  # noqa: BLE001 - un error de una escritura no corta el partido
            _log.exception("simulacion_paso_fallido que=%s", que)
        return None

    def _evento(self, p: _Partido, tipo: str, minuto: int, jugador: dict[str, Any]) -> None:
        p.eventos += 1
        id_evento = f"SIM-{p.codigo}-{p.inicio:%Y%m%d%H%M%S}-{p.eventos:02d}"
        self._paso("evento", lambda: self._neo4j.registrar_evento(p.codigo, {
            "id_evento": id_evento, "tipo": tipo, "minuto": minuto, "id_jugador": jugador["id_jugador"]}))

    def _estadisticas(self, p: _Partido, minuto: int) -> None:
        instante = int((p.inicio + timedelta(minutes=minuto)).timestamp())
        posesion = {p.local: p.posesion_local, p.visitante: 100 - p.posesion_local}
        lineas = [
            f"estadisticas_partido,partido_id={p.codigo},equipo_id={eq} "
            f"posesion_pct={posesion[eq]:.2f},pases_completados={p.pases[eq]}i,"
            f"tiros={p.tiros[eq]}i,usuarios_activos={p.usuarios[eq]}i {instante}"
            for eq in (p.local, p.visitante)
        ]
        self._paso("estadisticas", lambda: self._influx.escribir_estadisticas(lineas))

    def _relatar(self, p: _Partido, eq: str | None, minuto: int, texto: str) -> None:
        """`eq`: selección a la que se refiere el mensaje (gol, expulsión); None si es neutral."""
        self._paso("relato", lambda: self._cassandra.publicar_comentario({
            "codigo_partido": p.codigo, **RELATOR, "equipo_apoyado": eq,
            "texto": texto[:280], "minuto_partido": min(minuto, 130)}))

    def _hincha(self, p: _Partido, eq: str, minuto: int, tipo: str, jugador: str = "") -> None:
        """Un comentario de un hincha simulado de `eq`, con una frase al azar del tipo pedido."""
        if not p.hinchas.get(eq):
            return
        id_usuario, alias = p.rnd.choice(p.hinchas[eq])
        rival = self._rival(p, eq)
        texto = p.rnd.choice(FRASES[tipo]).format(
            eq=p.nombres[eq], rival=p.nombres[rival], jugador=jugador, sede=p.sede or "estadio",
            min=formato_minuto(minuto), marcador=f"{p.goles[eq]}-{p.goles[rival]}")
        self._paso("hincha", lambda: self._cassandra.publicar_comentario({
            "codigo_partido": p.codigo, "id_usuario": id_usuario, "usuario_alias": alias,
            "equipo_apoyado": eq, "texto": texto[:280], "minuto_partido": min(minuto, 130)}))

    def _reloj(self, p: _Partido, minuto: int, adicion: int, en_curso: bool) -> None:
        ttl = TTL_LATIDO_S if en_curso else TTL_FINAL_S
        self._paso("reloj", lambda: self._redis.actualizar_reloj(p.codigo, minuto, adicion, en_curso, ttl))

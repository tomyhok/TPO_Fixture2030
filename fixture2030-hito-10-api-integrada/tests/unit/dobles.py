"""Dobles en memoria de los adaptadores.

Implementan los mismos métodos públicos que los adaptadores reales y registran
cada llamada en `llamadas`, para comprobar que una entrada inválida no llega a
la fuente (RNF3). Asignar `falla` hace que la próxima operación lance ese error,
como lo haría el adaptador real al traducir una excepción del driver.
"""

import json
from datetime import UTC, datetime
from typing import Any

from app.core.errores import ErrorAPI
from app.core.metricas import metricas


class Doble:
    NOMBRE = "doble"

    def __init__(self) -> None:
        self.llamadas: list[str] = []
        self.falla: Exception | None = None

    def _usar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        # Igual que adapters/base.py: el ping de salud no cuenta como operación de negocio.
        registrar = operacion != "ping"
        if self.falla is not None:
            codigo = self.falla.codigo if isinstance(self.falla, ErrorAPI) else f"error_inesperado:{type(self.falla).__name__}"
            if registrar:
                metricas.registrar_operacion_db(self.NOMBRE, operacion, codigo, 0.002)
            raise self.falla
        if registrar:
            metricas.registrar_operacion_db(self.NOMBRE, operacion, "ok", 0.001)

    def ping(self) -> None:
        self._usar("ping")

    def cerrar(self) -> None:
        pass


class MongoDoble(Doble):
    NOMBRE = "mongodb"
    EQUIPOS = {
        "ARG": {"codigo_iso": "ARG", "nombre": "Argentina", "confederacion": "CONMEBOL", "grupo": "A",
                "ranking_fifa": 1, "director_tecnico": "Martinez", "pais_anfitrion": True},
        "ESP": {"codigo_iso": "ESP", "nombre": "Espana", "confederacion": "UEFA", "grupo": "K",
                "ranking_fifa": 11, "director_tecnico": "Keller", "pais_anfitrion": True},
    }
    def obtener_equipo(self, codigo_iso: str) -> dict[str, Any] | None:
        self._usar("obtener_equipo")
        return dict(self.EQUIPOS[codigo_iso]) if codigo_iso in self.EQUIPOS else None

    def listar_equipos(self) -> list[dict[str, Any]]:
        self._usar("listar_equipos")
        return [dict(e) for e in self.EQUIPOS.values()]

    def jugadores_equipo(self, codigo_iso: str) -> list[dict[str, Any]]:
        self._usar("jugadores_equipo")
        return [{"id_jugador": f"{codigo_iso}-10", "nombre": "Diez", "dorsal": 10, "posicion": "DEL"}]


class Neo4jDoble(Doble):
    NOMBRE = "neo4j"
    EVENTOS = {
        "P-001": [{"id_evento": "EV-001", "tipo": "Gol", "minuto": 23,
                   "jugador": {"id_jugador": "ARG-10", "nombre": "Andrés Fuentes"}}],
        "P-002": [],
    }


    def eventos_partido(self, codigo: str, limit: int):
        self._usar("eventos_partido")
        if codigo not in self.EVENTOS:
            return None
        return {"codigo_partido": codigo, "eventos": self.EVENTOS[codigo][:limit]}

    def listar_partidos(self):
        self._usar("listar_partidos")
        return [{"codigo_partido": "P-001", "fecha": "2030-06-10", "fase": "Grupos",
                 "sede": {"nombre": "Estadio Monumental", "ciudad": "Buenos Aires"},
                 "equipos": [{"codigo_iso": "ARG", "nombre": "Argentina", "condicion": "local"},
                             {"codigo_iso": "ESP", "nombre": "Espana", "condicion": "visitante"}]}]


class CassandraDoble(Doble):
    NOMBRE = "cassandra"

    def leer_muro(self, codigo, ventana, limit, cursor):
        self._usar("leer_muro")
        filas = [
            {"id_comentario": "2e379e0a-e506-11f5-800a-00000005f1c7", "codigo_partido": codigo,
             "ventana": ventana, "id_usuario": "U-1003", "usuario_alias": "tribuna_sur",
             "equipo_apoyado": "ARG", "texto": "Casi gol", "idioma": "es",
             "estado_moderacion": "publicado", "minuto_partido": 30,
             "creado_en": datetime(2030, 6, 15, 20, 16, 44, tzinfo=UTC)},
        ] if ventana == "203006152016" and cursor is None else []
        return filas[:limit], len(filas) > limit

    def __init__(self) -> None:
        super().__init__()
        self.publicados: list[dict[str, Any]] = []

    def leer_muro_ventanas(self, codigo, ventanas, limit):
        self._usar("leer_muro_ventanas")
        return [c for c in self.publicados if c["codigo_partido"] == codigo][:limit]

    def publicar_comentario(self, c):
        self._usar("publicar_comentario")
        fila = {**c, "id_comentario": "d116f974-e53a-11f1-b402-ea5fba123d87", "ventana": "203006102030",
                "idioma": "es", "estado_moderacion": "publicado", "creado_en": datetime(2030, 6, 10, 20, 30, tzinfo=UTC)}
        self.publicados = [fila, *self.publicados]
        return fila


class RedisDoble(Doble):
    NOMBRE = "redis"

    def __init__(self) -> None:
        super().__init__()
        self.sesiones = {"S-0001": {"usuario_id": "U-0001", "rol": "fan", "estado": "activa", "ttl_restante_s": 1700}}
        self.visitas: dict[str, int] = {}
        self.votos: dict[str, dict[str, int]] = {}
        self.votantes: dict[str, set[str]] = {}

    def leer_sesion(self, id_sesion):
        self._usar("leer_sesion")
        return dict(self.sesiones[id_sesion]) if id_sesion in self.sesiones else None

    def crear_sesion(self, alias, equipo_favorito, ttl_s):
        self._usar("crear_sesion")
        n = 5001 + sum(1 for k in self.sesiones if k.startswith("S-5"))
        self.sesiones[f"S-{n}"] = {"usuario_id": f"U-{n}", "rol": "fan", "estado": "activa",
                                   "ttl_restante_s": ttl_s, "alias": alias, "equipo_favorito": equipo_favorito}
        return {"id_sesion": f"S-{n}", "usuario_id": f"U-{n}", "ttl_restante_s": ttl_s}

    def leer_sesion_portal(self, id_sesion):
        self._usar("leer_sesion_portal")
        d = self.sesiones.get(id_sesion)
        if d is None:
            return None
        return {"id_sesion": id_sesion, "alias": d.get("alias") or d["usuario_id"],
                "equipo_favorito": d.get("equipo_favorito"),
                **{k: d[k] for k in ("usuario_id", "rol", "estado", "ttl_restante_s")}}

    def cerrar_sesion(self, id_sesion):
        self._usar("cerrar_sesion")
        return self.sesiones.pop(id_sesion, None) is not None

    def registrar_visita(self, codigo, usuario_id, id_sesion):
        self._usar("registrar_visita")
        self.visitas = {**self.visitas, codigo: self.visitas.get(codigo, 0) + 1}

    def estado_vivo(self, codigo, usuario_id):
        self._usar("estado_vivo")
        ranking = sorted(self.votos.get(codigo, {}).items(), key=lambda kv: -kv[1])
        return {"visitas": self.visitas.get(codigo, 0), "conectados": 0,
                "encuesta": [{"id_jugador": j, "votos": v} for j, v in ranking],
                "ya_voto": usuario_id in self.votantes.get(codigo, set())}

    def votar_figura(self, codigo, usuario_id, id_jugador):
        self._usar("votar_figura")
        votantes = self.votantes.setdefault(codigo, set())
        if usuario_id in votantes:
            return False
        votantes.add(usuario_id)
        votos = self.votos.setdefault(codigo, {})
        votos[id_jugador] = votos.get(id_jugador, 0) + 1
        return True


class InfluxDoble(Doble):
    NOMBRE = "influxdb"

    def __init__(self) -> None:
        super().__init__()
        self.ultimo_tope: int | None = None

    def serie_partido(self, codigo, equipo, desde, hasta, resolucion, tope):
        self._usar("serie_partido")
        self.ultimo_tope = tope
        if codigo != "P-001":
            return []
        filas = []
        for eq in ([equipo] if equipo else ["ARG", "ESP"]):
            filas.append({"instante": desde, "equipo_id": eq, "posesion_pct_prom": 50.0,
                          "pases_completados_max": 10, "tiros_max": 1, "usuarios_activos_max": 1000})
        return filas


class IrisDoble(Doble):
    NOMBRE = "iris"

    def __init__(self) -> None:
        super().__init__()
        self.actas = {
            "P-001": {"codigo_partido": "P-001", "sede": "Estadio Monumental", "fecha": "2030-06-10",
                      "estado": "En Juego", "arbitro": {"nombre": "Facundo", "apellido": "Tello", "rango": "FIFA"},
                      "eventos": []},
            "P-003": {"codigo_partido": "P-003", "sede": "Estadio Santiago Bernabeu", "fecha": "2030-06-16",
                      "estado": "Finalizado", "arbitro": {"nombre": "Facundo", "apellido": "Tello", "rango": "FIFA"},
                      "eventos": []},
        }

    def obtener_acta(self, codigo):
        self._usar("obtener_acta")
        if codigo not in self.actas:
            return None
        return json.loads(json.dumps(self.actas[codigo]))

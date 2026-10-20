"""Dobles en memoria de los adaptadores.

Implementan los mismos métodos públicos que los adaptadores reales y registran
cada llamada en `llamadas`, para comprobar que una entrada inválida no llega a
la fuente (RNF3). Asignar `falla` hace que la próxima operación lance ese error,
como lo haría el adaptador real al traducir una excepción del driver.
"""

import json
from datetime import UTC, datetime
from typing import Any


class Doble:
    def __init__(self) -> None:
        self.llamadas: list[str] = []
        self.falla: Exception | None = None

    def _usar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.falla is not None:
            raise self.falla

    def ping(self) -> None:
        self._usar("ping")

    def cerrar(self) -> None:
        pass


class MongoDoble(Doble):
    EQUIPOS = {
        "ARG": {"codigo_iso": "ARG", "nombre": "Argentina", "confederacion": "CONMEBOL", "grupo": "A",
                "ranking_fifa": 1, "director_tecnico": "Martinez", "pais_anfitrion": True},
        "ESP": {"codigo_iso": "ESP", "nombre": "Espana", "confederacion": "UEFA", "grupo": "K",
                "ranking_fifa": 11, "director_tecnico": "Keller", "pais_anfitrion": True},
    }
    def obtener_equipo(self, codigo_iso: str) -> dict[str, Any] | None:
        self._usar("obtener_equipo")
        return dict(self.EQUIPOS[codigo_iso]) if codigo_iso in self.EQUIPOS else None


class Neo4jDoble(Doble):
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


class CassandraDoble(Doble):

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


class RedisDoble(Doble):
    def __init__(self) -> None:
        super().__init__()
        self.sesiones = {"S-0001": {"usuario_id": "U-0001", "rol": "fan", "estado": "activa", "ttl_restante_s": 1700}}

    def leer_sesion(self, id_sesion):
        self._usar("leer_sesion")
        return dict(self.sesiones[id_sesion]) if id_sesion in self.sesiones else None


class InfluxDoble(Doble):
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

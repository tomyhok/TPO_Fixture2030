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
    JUGADORES = {
        "ARG-10": {"id_jugador": "ARG-10", "nombre": "Andrés Fuentes", "dorsal": 10, "posicion": "DEF",
                   "club_actual": "No informado", "fecha_nacimiento": "2004-10-18", "edad": 25,
                   "altura_cm": 179, "pie_habil": "izquierdo", "codigo_equipo": "ARG"},
    }

    def obtener_equipo(self, codigo_iso: str) -> dict[str, Any] | None:
        self._usar("obtener_equipo")
        return dict(self.EQUIPOS[codigo_iso]) if codigo_iso in self.EQUIPOS else None

    def existe_equipo(self, codigo_iso: str) -> bool:
        self._usar("existe_equipo")
        return codigo_iso in self.EQUIPOS

    def listar_equipos(self, confederacion, grupo, page, size):
        self._usar("listar_equipos")
        items = [
            {k: v for k, v in e.items() if k not in ("director_tecnico", "pais_anfitrion")}
            for e in self.EQUIPOS.values()
            if (confederacion is None or e["confederacion"] == confederacion)
            and (grupo is None or e["grupo"] == grupo)
        ]
        return items[(page - 1) * size : page * size], len(items)

    def listar_jugadores(self, codigo_equipo, posicion, page, size):
        self._usar("listar_jugadores")
        items = [
            {k: j[k] for k in ("id_jugador", "nombre", "dorsal", "posicion", "club_actual")}
            for j in self.JUGADORES.values()
            if j["codigo_equipo"] == codigo_equipo and (posicion is None or j["posicion"] == posicion)
        ]
        return items[(page - 1) * size : page * size], len(items)

    def obtener_jugador(self, id_jugador: str):
        self._usar("obtener_jugador")
        return dict(self.JUGADORES[id_jugador]) if id_jugador in self.JUGADORES else None


class Neo4jDoble(Doble):
    FICHAS = {
        "P-001": {"codigo_partido": "P-001", "fecha": "2030-06-10", "fase": "Grupos",
                  "local": {"codigo_iso": "ARG", "nombre": "Argentina"},
                  "visitante": {"codigo_iso": "ESP", "nombre": "Espana"},
                  "sede": {"codigo_sede": "MON", "nombre": "Estadio Monumental", "ciudad": "Buenos Aires"}},
        "P-002": {"codigo_partido": "P-002", "fecha": "2030-06-12", "fase": "Grupos",
                  "local": None, "visitante": None, "sede": None},
    }
    EVENTOS = {
        "P-001": [{"id_evento": "EV-001", "tipo": "Gol", "minuto": 23,
                   "jugador": {"id_jugador": "ARG-10", "nombre": "Andrés Fuentes"}}],
        "P-002": [],
    }

    def existe_partido(self, codigo: str) -> bool:
        self._usar("existe_partido")
        return codigo in self.FICHAS

    def ficha_partido(self, codigo: str):
        self._usar("ficha_partido")
        return dict(self.FICHAS[codigo]) if codigo in self.FICHAS else None

    def eventos_partido(self, codigo: str, limit: int):
        self._usar("eventos_partido")
        if codigo not in self.FICHAS:
            return None
        return {"codigo_partido": codigo, "eventos": self.EVENTOS[codigo][:limit]}

    def rivales(self, codigo_iso: str, limit: int):
        self._usar("rivales")
        if codigo_iso != "ARG":
            return None
        return {"codigo_iso": "ARG", "rivales": [
            {"codigo_iso": "ESP", "nombre": "Espana", "codigo_partido": "P-001",
             "fecha": "2030-06-10", "condicion": "local"}][:limit]}


class CassandraDoble(Doble):
    def __init__(self) -> None:
        super().__init__()
        self.publicados: list[dict[str, Any]] = []

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

    def publicar(self, comentario: dict[str, Any]) -> None:
        self._usar("publicar")
        self.publicados.append(comentario)


class RedisDoble(Doble):
    def __init__(self) -> None:
        super().__init__()
        self.sesiones = {"S-0001": {"usuario_id": "U-0001", "rol": "fan", "estado": "activa", "ttl_restante_s": 1700}}
        self.cache: dict[str, str] = {}
        self.idem: dict[str, str] = {}

    def leer_sesion(self, id_sesion):
        self._usar("leer_sesion")
        return dict(self.sesiones[id_sesion]) if id_sesion in self.sesiones else None

    def borrar_sesion(self, id_sesion):
        self._usar("borrar_sesion")
        return 1 if self.sesiones.pop(id_sesion, None) else 0

    def leer_cache_partido(self, codigo):
        self._usar("leer_cache_partido")
        return self.cache.get(codigo)

    def guardar_cache_partido(self, codigo, valor_json, ttl_s):
        self._usar("guardar_cache_partido")
        self.cache[codigo] = valor_json

    def reservar_idempotencia(self, clave, valor_json, ttl_s):
        self._usar("reservar_idempotencia")
        if clave in self.idem:
            return False
        self.idem[clave] = valor_json
        return True

    def leer_idempotencia(self, clave):
        self._usar("leer_idempotencia")
        return self.idem.get(clave)

    def completar_idempotencia(self, clave, valor_json):
        self._usar("completar_idempotencia")
        self.idem[clave] = valor_json

    def liberar_idempotencia(self, clave):
        self._usar("liberar_idempotencia")
        self.idem.pop(clave, None)


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
    TRANSICIONES = {("Programado", "En Juego"), ("En Juego", "Finalizado")}

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
            return {"ok": 0, "error": "NO_ENCONTRADO"}
        return {"ok": 1, "acta": json.loads(json.dumps(self.actas[codigo]))}

    def cambiar_estado(self, codigo, estado):
        self._usar("cambiar_estado")
        if codigo not in self.actas:
            return {"ok": 0, "error": "NO_ENCONTRADO"}
        acta = self.actas[codigo]
        if acta["estado"] == estado:
            return {"ok": 1, "cambiado": 0, "acta": acta}
        if (acta["estado"], estado) not in self.TRANSICIONES:
            return {"ok": 0, "error": "TRANSICION_INVALIDA", "estado_actual": acta["estado"]}
        acta["estado"] = estado
        return {"ok": 1, "cambiado": 1, "acta": acta}

    def registrar_evento(self, codigo, minuto, tipo, descripcion):
        self._usar("registrar_evento")
        if codigo not in self.actas:
            return {"ok": 0, "error": "NO_ENCONTRADO"}
        acta = self.actas[codigo]
        if acta["estado"] == "Finalizado":
            return {"ok": 0, "error": "PARTIDO_FINALIZADO", "estado_actual": "Finalizado"}
        evento = {"minuto": minuto, "tipo": tipo, "descripcion": descripcion}
        acta["eventos"].append(evento)
        return {"ok": 1, "evento": evento, "acta": acta}

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

    # Prode: mismas reglas que las colecciones y pipelines del adaptador real.
    def __init__(self) -> None:
        super().__init__()
        self.usuarios: dict[str, dict[str, Any]] = {}
        self.predicciones: dict[str, dict[str, Any]] = {}
        self.liquidaciones: dict[str, dict[str, int]] = {}

    def registrar_usuario_portal(self, alias, usuario_id, equipo_favorito):
        self._usar("registrar_usuario_portal")
        u = self.usuarios.setdefault(alias.lower(), {"usuario_id": usuario_id})
        u.update(alias=alias, equipo_favorito=equipo_favorito)
        return u["usuario_id"]

    def guardar_prediccion(self, p):
        self._usar("guardar_prediccion")
        clave = f"{p['codigo_partido']}:{p['usuario_id']}"
        previa = self.predicciones.get(clave)
        if previa and previa["puntos"] is not None:
            return None
        ahora = datetime.now(UTC)
        doc = {"creada_en": ahora, "acierto": None, "resultado_real": None, "puntos": None, **(previa or {}), **p,
               "resultado": _resultado(p["goles_local"], p["goles_visitante"]), "actualizada_en": ahora}
        self.predicciones[clave] = doc
        return dict(doc)

    def predicciones_usuario(self, usuario_id):
        self._usar("predicciones_usuario")
        return [dict(p) for _, p in sorted(self.predicciones.items()) if p["usuario_id"] == usuario_id]

    def resumen_predicciones(self, codigo, usuario_id):
        self._usar("resumen_predicciones")
        ps = [p for p in self.predicciones.values() if p["codigo_partido"] == codigo]
        conteo = {r: sum(1 for p in ps if p["resultado"] == r) for r in "LEV"}
        marcadores: dict[tuple[int, int], int] = {}
        for p in ps:
            k = (p["goles_local"], p["goles_visitante"])
            marcadores[k] = marcadores.get(k, 0) + 1
        mia = self.predicciones.get(f"{codigo}:{usuario_id}")
        return {
            "total": len(ps), "local": conteo["L"], "empate": conteo["E"], "visitante": conteo["V"],
            "promedio_goles_local": sum(p["goles_local"] for p in ps) / len(ps) if ps else None,
            "promedio_goles_visitante": sum(p["goles_visitante"] for p in ps) / len(ps) if ps else None,
            "marcadores": [{"goles_local": k[0], "goles_visitante": k[1], "cantidad": n}
                           for k, n in sorted(marcadores.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
            "mi_prediccion": dict(mia) if mia else None,
            "resultado_real": dict(self.liquidaciones[codigo]) if codigo in self.liquidaciones else None,
        }

    def partidos_pendientes(self):
        self._usar("partidos_pendientes")
        return sorted({p["codigo_partido"] for p in self.predicciones.values() if p["puntos"] is None})

    def liquidar_partido(self, codigo, goles_local, goles_visitante, puntos_exacto, puntos_resultado):
        self._usar("liquidar_partido")
        n = 0
        real = _resultado(goles_local, goles_visitante)
        for p in self.predicciones.values():
            if p["codigo_partido"] != codigo or p["puntos"] is not None:
                continue
            exacto = (p["goles_local"], p["goles_visitante"]) == (goles_local, goles_visitante)
            acierta = p["resultado"] == real
            p["acierto"] = "exacto" if exacto else "resultado" if acierta else "ninguno"
            p["puntos"] = puntos_exacto if exacto else puntos_resultado if acierta else 0
            p["resultado_real"] = {"goles_local": goles_local, "goles_visitante": goles_visitante}
            n += 1
        if n:
            self.liquidaciones[codigo] = {"goles_local": goles_local, "goles_visitante": goles_visitante}
        return n

    def tabla_posiciones(self, equipo, limit, usuario_id):
        self._usar("tabla_posiciones")
        filas: dict[str, dict[str, Any]] = {}
        for p in self.predicciones.values():
            u = next((x for x in self.usuarios.values() if x["usuario_id"] == p["usuario_id"]), {})
            f = filas.setdefault(p["usuario_id"], {
                "usuario_id": p["usuario_id"], "alias": u.get("alias", p["usuario_id"]),
                "equipo_favorito": u.get("equipo_favorito"),
                "puntos": 0, "exactos": 0, "aciertos": 0, "pronosticos": 0, "puntuados": 0})
            f["pronosticos"] += 1
            if p["puntos"] is not None:
                f["puntuados"] += 1
                f["puntos"] += p["puntos"]
                f["exactos"] += p["acierto"] == "exacto"
                f["aciertos"] += p["acierto"] in ("exacto", "resultado")
        lista = sorted((f for f in filas.values() if not equipo or f["equipo_favorito"] == equipo),
                       key=lambda f: (-f["puntos"], -f["exactos"], f["alias"]))
        for f in lista:  # $rank: los empates comparten puesto
            f["posicion"] = 1 + sum(1 for g in lista if (g["puntos"], g["exactos"]) > (f["puntos"], f["exactos"]))
        mia = next((f for f in lista if f["usuario_id"] == usuario_id), None)
        return {"filas": lista[:limit], "mi_fila": mia, "total_participantes": len(lista)}


def _resultado(gl: int, gv: int) -> str:
    return "L" if gl > gv else "V" if gl < gv else "E"


class Neo4jDoble(Doble):
    NOMBRE = "neo4j"
    EVENTOS = {
        "P-001": [{"id_evento": "EV-001", "tipo": "Gol", "minuto": 23,
                   "jugador": {"id_jugador": "ARG-10", "nombre": "Andrés Fuentes"}}],
        "P-002": [],
        "P-003": [{"id_evento": "EV-301", "tipo": "Gol", "minuto": 10,
                   "jugador": {"id_jugador": "URU-9", "nombre": "Nueve"}},
                  {"id_evento": "EV-302", "tipo": "Tarjeta Amarilla", "minuto": 80,
                   "jugador": {"id_jugador": "ESP-4", "nombre": "Cuatro"}}],
    }


    def eventos_partido(self, codigo: str, limit: int):
        self._usar("eventos_partido")
        if codigo not in self.EVENTOS:
            return None
        return {"codigo_partido": codigo, "eventos": self.EVENTOS[codigo][:limit]}

    def __init__(self) -> None:
        super().__init__()
        self.EVENTOS = json.loads(json.dumps(Neo4jDoble.EVENTOS))  # la simulación agrega eventos
        posiciones = ["ARQ"] + ["DEF"] * 4 + ["MED"] * 4 + ["DEL"] * 3
        self.jugadores = {iso: [{"codigo_iso": iso, "id_jugador": f"{iso}-{n}", "nombre": f"{iso} {n}",
                                 "posicion": pos} for n, pos in enumerate(posiciones, start=1)]
                          for iso in ("ARG", "ESP", "URU")}
        arbitro = {"nombre": "Facundo", "apellido": "Tello", "rango": "FIFA"}
        self.partidos = [
            {"codigo_partido": "P-001", "fecha": "2030-06-10", "fase": "Grupos", "estado": "En Juego",
             "sede": {"nombre": "Estadio Monumental", "ciudad": "Buenos Aires"}, "arbitro": arbitro,
             "equipos": [{"codigo_iso": "ARG", "nombre": "Argentina", "condicion": "local"},
                         {"codigo_iso": "ESP", "nombre": "Espana", "condicion": "visitante"}]},
            {"codigo_partido": "P-002", "fecha": "2030-06-12", "fase": "Grupos", "estado": "Programado",
             "sede": {"nombre": "Estadio Centenario", "ciudad": "Montevideo"}, "arbitro": arbitro,
             "equipos": [{"codigo_iso": "ARG", "nombre": "Argentina", "condicion": "visitante"},
                         {"codigo_iso": "URU", "nombre": "Uruguay", "condicion": "local"}]},
            {"codigo_partido": "P-003", "fecha": "2030-06-16", "fase": "Grupos", "estado": "Finalizado",
             "sede": {"nombre": "Estadio Santiago Bernabeu", "ciudad": "Madrid"}, "arbitro": None,
             "equipos": [{"codigo_iso": "ESP", "nombre": "Espana", "condicion": "local"},
                         {"codigo_iso": "URU", "nombre": "Uruguay", "condicion": "visitante"}]},
        ]

    def estado(self, codigo: str, nuevo: str) -> None:
        """Atajo de las pruebas para fijar el estado sin pasar por la API."""
        next(p for p in self.partidos if p["codigo_partido"] == codigo)["estado"] = nuevo

    def listar_partidos(self):
        self._usar("listar_partidos")
        filas = json.loads(json.dumps(self.partidos))
        for f in filas:  # como el adaptador real: goles por selección a partir de los eventos Gol
            f["goles"] = {e["codigo_iso"]: 0 for e in f["equipos"]}
            for ev in self.EVENTOS.get(f["codigo_partido"], []):
                if ev["tipo"].lower().startswith("gol") and ev.get("jugador"):
                    iso = ev["jugador"]["id_jugador"].split("-")[0]
                    f["goles"][iso] = f["goles"].get(iso, 0) + 1
        return filas

    def cambiar_estado(self, codigo, actual, nuevo, inicio=None):
        self._usar("cambiar_estado")
        p = next((p for p in self.partidos if p["codigo_partido"] == codigo), None)
        if p is None or p["estado"] != actual:
            return False
        p["estado"] = nuevo
        if inicio:
            p["inicio"] = inicio
        return True

    def jugadores_partido(self, codigo):
        self._usar("jugadores_partido")
        p = next((p for p in self.partidos if p["codigo_partido"] == codigo), None)
        isos = [e["codigo_iso"] for e in p["equipos"]] if p else []
        return [dict(j) for iso in isos for j in self.jugadores.get(iso, [])]

    def registrar_evento(self, codigo, evento):
        self._usar("registrar_evento")
        nombre = next(j["nombre"] for js in self.jugadores.values() for j in js if j["id_jugador"] == evento["id_jugador"])
        self.EVENTOS.setdefault(codigo, []).append({
            "id_evento": evento["id_evento"], "tipo": evento["tipo"], "minuto": evento["minuto"],
            "jugador": {"id_jugador": evento["id_jugador"], "nombre": nombre}})


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
        self.relojes: dict[str, dict[str, Any]] = {}

    def leer_sesion(self, id_sesion):
        self._usar("leer_sesion")
        return dict(self.sesiones[id_sesion]) if id_sesion in self.sesiones else None

    def crear_sesion(self, alias, equipo_favorito, ttl_s):
        self._usar("crear_sesion")
        n = 5001 + sum(1 for k in self.sesiones if k.startswith("S-5"))
        self.sesiones[f"S-{n}"] = {"usuario_id": f"U-{n}", "rol": "fan", "estado": "activa",
                                   "ttl_restante_s": ttl_s, "alias": alias, "equipo_favorito": equipo_favorito}
        return {"id_sesion": f"S-{n}", "usuario_id": f"U-{n}", "ttl_restante_s": ttl_s}

    def asignar_usuario_sesion(self, id_sesion, usuario_id):
        self._usar("asignar_usuario_sesion")
        self.sesiones[id_sesion]["usuario_id"] = usuario_id

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
        return {"visitas": self.visitas.get(codigo, 0), "conectados": 0,
                "reloj": dict(self.relojes[codigo]) if codigo in self.relojes else None}

    def leer_reloj(self, codigo):
        self._usar("leer_reloj")
        return dict(self.relojes[codigo]) if codigo in self.relojes else None

    def actualizar_reloj(self, codigo, minuto, adicion, en_curso, ttl_s):
        self._usar("actualizar_reloj")
        self.relojes[codigo] = {"minuto": minuto, "adicion": adicion, "en_curso": en_curso}



class InfluxDoble(Doble):
    NOMBRE = "influxdb"

    def __init__(self) -> None:
        super().__init__()
        self.ultimo_tope: int | None = None
        self.lineas: list[str] = []

    def escribir_estadisticas(self, lineas):
        self._usar("escribir_estadisticas")
        self.lineas.extend(lineas)

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

"""Pruebas de la API del Hito 10: cadena cliente HTTP -> API -> adaptador -> producto (RF15, sección 5.5).

Solo se usan rutas GET: ninguna prueba escribe datos de dominio (RNF6).
La API corregida consulta cada fuente sin caché Redis sobre Neo4j.

Cada request lleva un X-Request-ID propio (`h11-<corrida>-<n>`) para encontrar
después las líneas del log de la API que le corresponden (RF19).
"""

import socket
import urllib.error
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from conectividad.config import Config
from conectividad.red import http
from conectividad.registro import FAIL, OK, SKIP, WARN, Registro, Resultado, ahora

# Clases de resultado que la evaluación debe distinguir (sección 5.5).
EXITO = "exito"
VACIO = "respuesta_vacia_valida"
INEXISTENTE = "recurso_inexistente"
VALIDACION = "error_validacion"
NO_DISPONIBLE = "dependencia_no_disponible"
TIMEOUT = "dependencia_timeout"
INTERNO = "error_interno"
NO_ALCANZABLE = "api_no_alcanzable"


@dataclass
class Caso:
    nombre: str
    path: str
    dependencias: list[str]
    esperado: set[str]
    params: dict[str, Any] = field(default_factory=dict)
    nota: str = ""


CASOS = [
    Caso("liveness", "/health/live", [], {EXITO}, nota="no consulta bases"),
    Caso("readiness", "/health/ready", ["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"], {EXITO},
         nota="diagnóstico reutilizado (TTL)"),
    Caso("diagnóstico por dependencia", "/health/dependencias",
         ["mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"], {EXITO}, {"refrescar": "true"}),
    Caso("CU01 equipo", "/equipos/ARG", ["mongodb"], {EXITO}),
    Caso("CU01 equipo inexistente", "/equipos/XYZ", ["mongodb"], {INEXISTENTE}),
    Caso("CU01 código inválido", "/equipos/arg", [], {VALIDACION}, nota="no llega a la base"),
    Caso("CU06 eventos", "/partidos/P-001/eventos", ["neo4j"], {EXITO}, {"limit": 5}),
    Caso("CU06 partido sin eventos", "/partidos/P-002/eventos", ["neo4j"], {VACIO}),
    Caso("CU06 partido inexistente", "/partidos/P-999/eventos", ["neo4j"], {INEXISTENTE}),
    Caso("CU08 muro de comentarios", "/partidos/P-001/comentarios", ["cassandra"], {EXITO},
         {"ventana": "203006152015", "limit": 5}),
    Caso("CU08 ventana sin comentarios", "/partidos/P-001/comentarios", ["cassandra"], {VACIO},
         {"ventana": "203001010000"}),
    Caso("CU10 sesión", "/sesiones/S-0001", ["redis"], {EXITO, INEXISTENTE},
         nota="las sesiones de muestra expiran a los 30 min: 404 SESION_NO_VIGENTE también es válido"),
    Caso("CU12 estadísticas", "/partidos/P-001/estadisticas", ["influxdb"], {EXITO},
         {"desde": "2030-06-10T20:00:00Z", "hasta": "2030-06-10T20:15:00Z", "resolucion": "5m"}),
    Caso("CU12 ventana sin puntos", "/partidos/P-001/estadisticas", ["influxdb"], {VACIO},
         {"desde": "2031-01-01T00:00:00Z", "hasta": "2031-01-01T01:00:00Z"}),
    Caso("CU12 intervalo invertido", "/partidos/P-001/estadisticas", [], {VALIDACION},
         {"desde": "2030-06-10T22:00:00Z", "hasta": "2030-06-10T20:00:00Z"}),
    Caso("CU13 acta oficial", "/partidos-oficiales/P-009", ["iris"], {EXITO}),
    Caso("CU13 acta inexistente", "/partidos-oficiales/P-999", ["iris"], {INEXISTENTE}),
]

LISTAS = ("items", "eventos", "series", "rivales")


def clasificar(status: int, cuerpo: Any) -> str:
    if 200 <= status < 300:
        if isinstance(cuerpo, dict) and any(isinstance(cuerpo.get(k), list) and not cuerpo[k] for k in LISTAS):
            return VACIO
        return EXITO
    return {400: VALIDACION, 404: INEXISTENTE, 503: NO_DISPONIBLE, 504: TIMEOUT, 500: INTERNO}.get(status, f"http_{status}")


def _resumen(cuerpo: Any) -> str:
    if not isinstance(cuerpo, dict):
        return ""
    if "error" in cuerpo:
        e = cuerpo["error"]
        dep = ",".join(d.get("dependencia", "") for d in e.get("detalles", []) if "dependencia" in d)
        return f"{e.get('codigo')}{f' (dependencia={dep})' if dep else ''}"
    if "dependencias" in cuerpo and "estado" in cuerpo:
        estados = " ".join(f"{d['nombre']}={d['estado']}" for d in cuerpo["dependencias"])
        return f"estado={cuerpo['estado']} {estados}"
    if "listo" in cuerpo:
        return f"listo={cuerpo['listo']} estado={cuerpo['estado']} no_disponibles={cuerpo['no_disponibles']}"
    for clave in LISTAS:
        if isinstance(cuerpo.get(clave), list):
            return f"{clave}: {len(cuerpo[clave])}"
    for clave in ("nombre", "codigo_partido", "estado", "id_sesion"):
        if clave in cuerpo:
            return f"{clave}={cuerpo[clave]}"
    return ", ".join(list(cuerpo)[:4])


def evaluar(cfg: Config, registro: Registro, productos: list[str]) -> list[dict[str, Any]]:
    base = cfg.get("API_URL").rstrip("/")
    timeout_s = cfg.decimal("API_TIMEOUT_S")
    corrida = uuid.uuid4().hex[:6]
    casos = [c for c in CASOS if not c.dependencias or set(c.dependencias) & set(productos)]
    trazas: list[dict[str, Any]] = []
    alcanzable = True

    for n, caso in enumerate(casos, start=1):
        request_id = f"h11-{corrida}-{n:02d}"
        path = caso.path + (f"?{urlencode(caso.params)}" if caso.params else "")
        destino = f"GET {base}{path}"
        datos: dict[str, Any] = {"request_id": request_id, "dependencias": caso.dependencias, "metodo": "GET",
                                 "path": path, "esperado": sorted(caso.esperado)}
        if not alcanzable:
            registro.agregar(Resultado("api", "api", caso.nombre, SKIP, "no ejecutada: la API no es alcanzable",
                                       destino, ahora(), datos=datos))
            continue
        try:
            r = http("GET", f"{base}{path}", timeout_s, headers={"X-Request-ID": request_id})
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = None
            clase = clasificar(r.status, cuerpo)
            status, ms = r.status, r.duracion_ms
            eco = r.headers.get("x-request-id")
        except (urllib.error.URLError, OSError) as exc:
            razon = getattr(exc, "reason", exc)
            timeout = isinstance(razon, (TimeoutError, socket.timeout)) or isinstance(exc, (TimeoutError, socket.timeout))
            clase, status, ms, eco, cuerpo = ("timeout_cliente" if timeout else NO_ALCANZABLE), None, None, None, None
            if not timeout:
                alcanzable = False

        datos.update({"status": status, "clase": clase, "x_request_id": eco, "resumen": _resumen(cuerpo)})
        detalle = f"HTTP {status if status else '---'} -> {clase}"
        if datos["resumen"]:
            detalle += f" | {datos['resumen']}"
        if caso.nota:
            detalle += f" [{caso.nota}]"
        if clase in caso.esperado:
            estado, hip, sig = OK, "", ""
        elif clase == NO_ALCANZABLE:
            estado = FAIL
            datos["dependencias"] = list(productos)
            hip = "La API no está escuchando en API_URL (proceso detenido, otro puerto u otro host)."
            sig = "Iniciar la API (scripts/iniciar_api.sh del Hito 10) o corregir API_URL. Las rutas restantes no se ejecutan."
        elif clase in (NO_DISPONIBLE, TIMEOUT):
            estado = FAIL
            hip = (f"API alcanzable, dependencia fallida: {datos['resumen']}. "
                   "La API identifica la fuente en lugar de responder 200 vacío.")
            sig = "Contrastar con las pruebas nativas del mismo producto: si el cliente nativo funciona, revisar la configuración de la API."
        elif clase == INTERNO:
            estado = FAIL
            hip = "Error interno de la API: el detalle técnico está solo en el log."
            sig = f"Buscar request_id={request_id} en el log de la API."
        else:
            estado = WARN
            hip = f"Se esperaba {sorted(caso.esperado)} y se obtuvo {clase}."
            sig = "Revisar datos de prueba o el contrato de la ruta."
        afectadas = sorted(set(
            [d["nombre"] for d in cuerpo.get("dependencias", []) if d.get("estado") != "up"]
            + cuerpo.get("no_disponibles", [])
        )) if isinstance(cuerpo, dict) else []
        if estado == OK and afectadas:
            # La ruta de diagnóstico respondió bien, pero informa fuentes afectadas.
            estado = WARN
            hip = f"El diagnóstico de la API informa fuentes no disponibles: {', '.join(afectadas)}."
            sig = "Ver la fila de esas fuentes en la matriz y sus pruebas nativas."
            datos["dependencias"] = afectadas
            datos["degrada"] = True
        if eco and eco != request_id:
            estado, hip = WARN, f"La API no devolvió el X-Request-ID enviado ({eco})."
        registro.agregar(Resultado("api", "api", caso.nombre, estado, detalle, destino, ahora(),
                                   None if ms is None else round(ms, 1), hip, sig, datos))
        trazas.append(datos)
    return trazas


def lineas_de_log(cfg: Config, request_ids: list[str]) -> dict[str, list[str]]:
    """Líneas del log de la API asociadas a cada request ID (se redactan al escribirlas)."""
    ruta: Path = cfg.ruta("API_LOG_FILE")
    if not ruta.exists() or not request_ids:
        return {}
    buscados = set(request_ids)
    encontradas: dict[str, list[str]] = {rid: [] for rid in request_ids}
    with ruta.open(encoding="utf-8", errors="replace") as archivo:
        for linea in archivo:
            if "request_id=h11-" not in linea:
                continue
            rid = linea.split("request_id=", 1)[1].split()[0]
            if rid in buscados:
                encontradas[rid].append(linea.rstrip())
    return encontradas

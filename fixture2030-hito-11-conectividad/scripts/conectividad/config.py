"""Configuración externa del diagnóstico (RF3, RNF7, RNF13).

Cada variable se toma, de menor a mayor prioridad, de:
  1. los valores por defecto de este módulo (sin secretos);
  2. el `.env` de la API del Hito 10 (la misma configuración que usa la API);
  3. `config/conectividad.env` del Hito 11 (opcional, excluido del repositorio);
  4. variables de entorno del proceso (permiten simular escenarios sin editar archivos).

Se registra el origen de cada valor para poder explicar desde dónde salió un
host o un puerto. Los secretos solo se informan como "definida", "vacía" o
"sin completar"; su valor nunca se imprime.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

HITO = Path(__file__).resolve().parents[2]
RAIZ = HITO.parent
ENV_HITO10 = RAIZ / "fixture2030-hito-10-api-integrada" / ".env"
ENV_LOCAL = HITO / "config" / "conectividad.env"

DEFECTOS: dict[str, str] = {
    # --- API del Hito 10 ---
    "API_URL": "http://127.0.0.1:8000",
    "API_TIMEOUT_S": "15",
    "API_LOG_FILE": "../fixture2030-hito-10-api-integrada/logs/api.log",
    # --- Límites de espera (RNF5): los mismos nombres que usa la API ---
    "TIMEOUT_CONEXION_S": "2",
    "TIMEOUT_OPERACION_S": "5",
    "TCP_TIMEOUT_S": "3",
    "UMBRAL_LENTO_MS": "1000",
    # --- MongoDB (Hito 4) ---
    "MONGO_HOST": "127.0.0.1",
    "MONGO_PORT": "27017",
    "MONGO_USER": "",
    "MONGO_PASSWORD": "",
    "MONGO_AUTH_DB": "admin",
    "MONGO_DATABASE": "fixture2030",
    "MONGO_COLECCIONES": "equipos,jugadores",
    "MONGO_EQUIPO_PRUEBA": "ARG",
    # --- Neo4j (Hito 5) ---
    "NEO4J_URI": "bolt://127.0.0.1:7687",
    "NEO4J_HTTP_URL": "http://127.0.0.1:7474",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "",
    "NEO4J_DATABASE": "neo4j",
    "NEO4J_PARTIDO_PRUEBA": "P-001",
    "NEO4J_PARTIDO_SIN_EVENTOS": "P-002",
    # --- Cassandra (Hito 6) ---
    "CASSANDRA_HOSTS": "127.0.0.1",
    "CASSANDRA_PORT": "9042",
    "CASSANDRA_KEYSPACE": "fixture2030",
    "CASSANDRA_DC": "datacenter1",
    "CASSANDRA_TABLA": "comentarios_por_partido",
    "CASSANDRA_PARTIDO_PRUEBA": "P-001",
    "CASSANDRA_VENTANA_PRUEBA": "203006152015",
    # --- Redis (Hito 7) ---
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
    "REDIS_CLAVE_PRUEBA": "sesion:S-0001",
    "REDIS_SONDA_EXPIRACION": "0",
    # --- InfluxDB 3 Core (Hito 8) ---
    "INFLUX_URL": "http://127.0.0.1:8181",
    "INFLUX_DATABASE": "fixture2030",
    "INFLUX_TOKEN": "",
    "INFLUX_TOKEN_FILE": "../fixture2030-influxDB/.influxdb3-token",
    "INFLUX_TABLA": "estadisticas_partido",
    "INFLUX_PARTIDO_PRUEBA": "P-001",
    "INFLUX_DESDE": "2030-06-10T20:00:00Z",
    "INFLUX_HASTA": "2030-06-10T20:15:00Z",
    # --- InterSystems IRIS (Hito 9) ---
    "IRIS_HOST": "127.0.0.1",
    "IRIS_PORT": "1972",
    "IRIS_PORTAL_URL": "http://127.0.0.1:52773/csp/sys/UtilHome.csp",
    "IRIS_NAMESPACE": "USER",
    "IRIS_NAMESPACE_ALTERNATIVO": "USER",
    "IRIS_USER": "fixture_api",
    "IRIS_PASSWORD": "",
    "IRIS_CLASE": "Fixture.API",
    "IRIS_ACTA_PRUEBA": "P-001",
    # --- Docker (solo para informar el estado del contenedor) ---
    "DOCKER_PREFIJO": "fixture2030-",
}

_SECRETA = re.compile(r"PASSWORD|TOKEN$|SECRET", re.IGNORECASE)
_PLACEHOLDER = "<completar>"


def es_secreta(nombre: str) -> bool:
    return bool(_SECRETA.search(nombre)) and not nombre.endswith("_FILE")


def leer_env(ruta: Path) -> dict[str, str]:
    """Lee KEY=VALUE sin ejecutar el archivo (no se expanden variables ni comandos)."""
    valores: dict[str, str] = {}
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valores
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        valores[clave.strip()] = valor
    return valores


def _relativa(ruta: Path) -> str:
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return str(ruta)


class Config:
    def __init__(self, entorno: dict[str, str] | None = None):
        entorno = dict(os.environ if entorno is None else entorno)
        env_hito10 = Path(entorno["HITO10_ENV"]) if entorno.get("HITO10_ENV") else ENV_HITO10
        self.archivos: list[str] = []
        self._valores: dict[str, str] = {}
        self._origen: dict[str, str] = {}

        capas = [("defecto", DEFECTOS)]
        for ruta in (env_hito10, ENV_LOCAL):
            contenido = leer_env(ruta)
            if contenido:
                self.archivos.append(_relativa(ruta))
                capas.append((f"archivo {_relativa(ruta)}", contenido))
        capas.append(("variable de entorno", {k: v for k, v in entorno.items() if k in DEFECTOS}))
        for origen, valores in capas:
            for clave, valor in valores.items():
                if clave in DEFECTOS:
                    self._valores[clave] = valor
                    self._origen[clave] = origen

    # ------------------------------------------------------------ lectura
    def get(self, clave: str) -> str:
        return self._valores[clave]

    def entero(self, clave: str) -> int:
        return int(self.get(clave))

    def decimal(self, clave: str) -> float:
        return float(self.get(clave))

    def lista(self, clave: str) -> list[str]:
        return [v.strip() for v in self.get(clave).split(",") if v.strip()]

    def origen(self, clave: str) -> str:
        return self._origen.get(clave, "defecto")

    def ruta(self, clave: str) -> Path:
        ruta = Path(self.get(clave))
        return ruta if ruta.is_absolute() else (HITO / ruta).resolve()

    def falta(self, clave: str) -> bool:
        valor = self.get(clave).strip()
        return not valor or valor == _PLACEHOLDER

    # ----------------------------------------------------------- secretos
    def mostrar(self, clave: str) -> str:
        """Valor apto para imprimir: los secretos nunca se muestran."""
        valor = self.get(clave)
        if es_secreta(clave):
            if not valor.strip():
                return "(vacía)"
            return "(sin completar)" if valor.strip() == _PLACEHOLDER else "(definida, oculta)"
        return valor if valor else "(vacía)"

    def token_influx(self) -> tuple[str, str]:
        """Token de InfluxDB y su origen descriptivo (sin el valor)."""
        token = self.get("INFLUX_TOKEN").strip()
        if token and token != _PLACEHOLDER:
            return token, f"INFLUX_TOKEN ({self.origen('INFLUX_TOKEN')})"
        ruta = self.ruta("INFLUX_TOKEN_FILE")
        try:
            return ruta.read_text(encoding="utf-8").strip(), f"archivo {_relativa(ruta)}"
        except OSError:
            return "", f"sin token (no existe {_relativa(ruta)})"

    def secretos(self) -> tuple[list[str], int]:
        """Valores a ocultar en la salida y cuántos secretos no se pueden ocultar por valor.

        Un secreto igual a un valor público de la configuración (database, host...)
        no se oculta por valor: taparía el contexto en todo el diagnóstico. Igual no
        se imprime nunca, porque ninguna prueba muestra valores secretos.
        """
        publicos = [v for k, v in self._valores.items() if not es_secreta(k) and v]
        valores = [v.strip() for k, v in self._valores.items() if es_secreta(k) and len(v.strip()) >= 4]
        token, _ = self.token_influx()
        if token:
            valores.append(token)
        valores = [v for v in valores if v != _PLACEHOLDER]
        ocultables = [v for v in valores if not any(v in p for p in publicos)]
        return ocultables, len(valores) - len(ocultables)


def host_puerto(url: str, puerto_defecto: int) -> tuple[str, int]:
    partes = urlsplit(url)
    return partes.hostname or "", partes.port or puerto_defecto

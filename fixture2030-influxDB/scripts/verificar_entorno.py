"""Identifica la imagen real, contrasta los dos Compose y prueba el token, sin guardar secretos.

Uso (desde la raíz del repositorio o desde fixture2030-influxDB/):
    python fixture2030-influxDB/scripts/verificar_entorno.py

Sobrescribe docs/evidencia/08_entorno.json: siempre queda una sola versión vigente.
"""
import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
RAIZ = MODULO.parent
URL = "http://127.0.0.1:8181"
DATABASE = "fixture2030"


def docker(*args):
    return subprocess.check_output(["docker", *args], cwd=RAIZ, text=True, encoding="utf-8")


def http(metodo, ruta, token=None, cuerpo=None):
    """Devuelve (código HTTP, cuerpo JSON o texto). El token solo viaja en la cabecera."""
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    pedido = urllib.request.Request(URL + ruta, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto.strip().startswith(("[", "{")) else texto
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:120]


def comprobar_token():
    archivo = MODULO / ".influxdb3-token"
    if not archivo.exists():
        return {"origen": ".influxdb3-token", "presente": False}
    token = archivo.read_text(encoding="utf-8").strip()
    _, databases = http("GET", "/api/v3/configure/database?format=json", token)
    _, conteo = http("POST", "/api/v3/query_sql", token, {
        "db": DATABASE, "format": "json",
        "q": "SELECT partido_id, COUNT(*) AS puntos, MIN(time) AS primero, MAX(time) AS ultimo "
             "FROM estadisticas_partido GROUP BY partido_id ORDER BY partido_id"})
    return {
        "origen": ".influxdb3-token (valor no registrado)",
        "presente": True,
        "health_sin_token": http("GET", "/health")[0],
        "health_con_token": http("GET", "/health", token)[0],
        "token_invalido": http("GET", "/api/v3/configure/database", "token-invalido")[0],
        "databases": [d.get("iox::database") for d in databases] if isinstance(databases, list) else databases,
        "puntos_por_partido": conteo,
    }


def main():
    fecha = datetime.now(timezone.utc)
    archivos = [RAIZ / "docker-compose.yml", MODULO / "docker-compose.yml"]
    servicios = []
    for archivo in archivos:
        # Sin interpolar: InfluxDB no usa variables y así no hace falta el .env con las
        # credenciales de los OTROS servicios. Solo se guarda el servicio InfluxDB.
        cfg = json.loads(docker("compose", "-f", str(archivo), "config", "--no-interpolate", "--format", "json"))
        servicio = cfg["services"]["influxdb"]
        servicios.append({k: servicio.get(k) for k in ("image", "command", "ports", "volumes")})
    if servicios[0] != servicios[1]:
        raise RuntimeError("Los parámetros del servicio InfluxDB difieren entre los Compose.")
    container = json.loads(docker("inspect", "fixture2030-influxdb"))[0]
    if container["Config"]["Image"] != servicios[0]["image"] or container["Config"]["Cmd"] != servicios[0]["command"]:
        raise RuntimeError("El contenedor no ejecuta la imagen/comando del Compose entregado.")
    image = json.loads(docker("image", "inspect", container["Image"]))[0]
    puertos = container["HostConfig"]["PortBindings"]
    informe = {"fecha_utc": fecha.isoformat(), "servicio_coincidente": servicios[0],
        "imagen_configurada": container["Config"]["Image"], "image_id": container["Image"],
        "digests": image.get("RepoDigests", []),
        "version": docker("exec", "fixture2030-influxdb", "influxdb3", "--version").strip(),
        "runtime": {"contenedor_creado": container["Created"], "puertos": puertos,
                    "puerto_solo_localhost": all(p.get("HostIp") == "127.0.0.1" for b in puertos.values() for p in b),
                    "montajes": [{k: m.get(k) for k in ("Type", "Source", "Destination", "RW")} for m in container["Mounts"]]},
        "compose_sha256": {str(p.relative_to(RAIZ)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in archivos},
        "acceso": comprobar_token(),
        "limite": "Verifica entorno, token y datos presentes. No repite la carga histórica de 10M de puntos."}
    out = MODULO / "docs" / "evidencia" / "08_entorno.json"
    out.write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Ambos Compose coinciden. {informe['version']}. Evidencia: {out.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

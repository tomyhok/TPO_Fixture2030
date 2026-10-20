"""Identifica la imagen real y contrasta los dos Compose, sin consultar secretos."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
RAIZ = MODULO.parent


def docker(*args):
    return subprocess.check_output(["docker", *args], cwd=RAIZ, text=True, encoding="utf-8")


def main():
    fecha = datetime.now(timezone.utc)
    archivos = [RAIZ / "docker-compose.yml", MODULO / "docker-compose.yml"]
    servicios = []
    for archivo in archivos:
        # The expanded Compose can contain credentials for OTHER services.
        # Keep only the InfluxDB service, never print or persist the full config.
        cfg = json.loads(docker("compose", "-f", str(archivo), "config", "--format", "json"))
        servicio = cfg["services"]["influxdb"]
        servicios.append({k: servicio.get(k) for k in ("image", "command", "ports", "volumes")})
    if servicios[0] != servicios[1]:
        raise RuntimeError("Los parámetros del servicio InfluxDB difieren entre los Compose.")
    container = json.loads(docker("inspect", "fixture2030-influxdb"))[0]
    if container["Config"]["Image"] != servicios[0]["image"] or container["Config"]["Cmd"] != servicios[0]["command"]:
        raise RuntimeError("El contenedor no ejecuta la imagen/comando del Compose entregado.")
    image = json.loads(docker("image", "inspect", container["Image"]))[0]
    informe = {"fecha_utc": fecha.isoformat(), "servicio_coincidente": servicios[0],
        "imagen_configurada": container["Config"]["Image"], "image_id": container["Image"],
        "digests": image.get("RepoDigests", []),
        "version": docker("exec", "fixture2030-influxdb", "influxdb3", "--version").strip(),
        "runtime": {"puertos": container["NetworkSettings"]["Ports"],
                    "montajes": [{k: m.get(k) for k in ("Type", "Source", "Destination", "RW")} for m in container["Mounts"]]},
        "compose_sha256": {str(p.relative_to(RAIZ)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archivos},
        "limite": "Verifica entorno. No demuestra carga ni consultas; requieren token y ejecución separada."}
    out = MODULO / "docs" / fecha.strftime("entorno_%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    (out / "entorno.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ambos Compose coinciden. {informe['version']}. Evidencia: {out}")


if __name__ == "__main__":
    main()

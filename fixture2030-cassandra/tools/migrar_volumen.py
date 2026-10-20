"""Migra el bind mount existente al volumen nombrado, sin borrar el origen.

Ejecutar desde cualquier carpeta: python tools/migrar_volumen.py
Detiene Cassandra para copiar archivos consistentes; verifica SHA256 y recrea
solo ese servicio con el Compose raíz. Si falla, restaura el bind mount.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
NOMBRE = "fixture2030-cassandra"
VOLUMEN = "fixture2030_cassandra_data"


def docker(*args, comprobar=True):
    p = subprocess.run(["docker", *args], cwd=ROOT, capture_output=True, text=True)
    if comprobar and p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p


def main():
    previo = json.loads(docker("inspect", NOMBRE).stdout)[0]
    montaje = next(m for m in previo["Mounts"] if m["Destination"] == "/var/lib/cassandra")
    if montaje["Type"] == "volume" and montaje["Name"] == VOLUMEN:
        print("El servicio ya usa el volumen nombrado; no se copia ni modifica nada.")
        return
    if montaje["Type"] != "bind":
        raise RuntimeError("El origen no es un bind mount; revisar manualmente antes de migrar.")
    imagen = previo["Image"]
    docker("volume", "create", VOLUMEN)

    def auxiliar(comando):
        return docker("run", "--rm", "--user", "0", "--volumes-from", NOMBRE + ":ro",
                      "-v", VOLUMEN + ":/destino", "--entrypoint", "sh", imagen, "-c", comando).stdout

    auxiliar('test -z "$(find /destino -mindepth 1 -maxdepth 1 -print -quit)"')
    activo = previo["State"]["Running"]
    recreado = False
    try:
        if activo:
            print("Deteniendo Cassandra antes de copiar...", flush=True)
            docker("stop", NOMBRE)
        manifestar = "find . -type f -exec sha256sum '{}' ';' | sort"
        antes = auxiliar("cd /var/lib/cassandra && " + manifestar)
        auxiliar("cp -a /var/lib/cassandra/. /destino/")
        despues = auxiliar("cd /destino && " + manifestar)
        if antes != despues:
            raise RuntimeError("Los archivos copiados no coinciden; se conserva el origen.")
        print("Copia verificada por SHA256; el directorio original se conserva.", flush=True)
        recreado = True
        docker("compose", "up", "-d", "--no-deps", "--pull", "never", "cassandra")
        limite = time.monotonic() + 240
        while time.monotonic() < limite:
            actual = json.loads(docker("inspect", NOMBRE).stdout)[0]
            if actual["State"].get("Health", {}).get("Status") == "healthy":
                break
            time.sleep(3)
        else:
            raise RuntimeError("Cassandra no llegó a healthy dentro del límite.")
        actual = json.loads(docker("inspect", NOMBRE).stdout)[0]
        destino = next(m for m in actual["Mounts"] if m["Destination"] == "/var/lib/cassandra")
        assert destino["Type"] == "volume" and destino["Name"] == VOLUMEN
        resultado = {"origen": "bind mount conservado", "destino": VOLUMEN,
                     "tipo": destino["Type"], "archivos_verificados": len(antes.splitlines()),
                     "sha256_manifiesto": hashlib.sha256(antes.encode()).hexdigest(),
                     "hashes_coinciden": True, "estado": "healthy", "imagen_id": actual["Image"]}
        evidencia = ROOT / "fixture2030-cassandra/docs/revision_2026-10-19"
        evidencia.mkdir(parents=True, exist_ok=True)
        (evidencia / "migracion_volumen.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
        print(json.dumps(resultado, indent=2))
    except Exception:
        if recreado:
            # Override temporal para volver al origen íntegro, nunca para borrarlo.
            with tempfile.TemporaryDirectory(prefix="fixture-cassandra-rollback-") as carpeta:
                override = Path(carpeta) / "rollback.json"
                override.write_text(json.dumps({"services": {"cassandra": {"volumes": [
                    {"type": "bind", "source": montaje["Source"], "target": "/var/lib/cassandra"}
                ]}}}), encoding="utf-8")
                docker("compose", "-f", str(ROOT / "docker-compose.yml"), "-f", str(override),
                       "up", "-d", "--no-deps", "--pull", "never", "cassandra")
        elif activo:
            docker("start", NOMBRE)
        raise


if __name__ == "__main__":
    main()

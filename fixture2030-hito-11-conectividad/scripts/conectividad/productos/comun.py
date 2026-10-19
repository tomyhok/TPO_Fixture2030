"""Pruebas comunes a todos los productos: configuración y estado del contenedor."""

import shutil
import subprocess
from pathlib import Path

from conectividad.config import Config, es_secreta
from conectividad.red import LimiteExcedido
from conectividad.registro import Cadena, Paso, fail, ok, resumen_excepcion, skip, warn


def capa_configuracion(cadena: Cadena, cfg: Config, variables: list[str], obligatorias: list[str]) -> None:
    """Muestra la configuración efectiva (secretos ocultos) y bloquea la cadena si falta algo."""
    faltan = [v for v in obligatorias if cfg.falta(v)]

    def prueba() -> Paso:
        partes = [f"{v} {cfg.mostrar(v)}" if es_secreta(v) else f"{v}={cfg.mostrar(v)}" for v in variables]
        origenes = sorted({cfg.origen(v) for v in variables})
        detalle = "; ".join(partes) + f" [origen: {', '.join(origenes)}]"
        if faltan:
            return Paso(
                "WARN",
                f"faltan {', '.join(faltan)} -> producto no configurado en este entorno. {detalle}",
                "Sin estas variables no se puede intentar la conexión: el resultado es 'no configurado', no 'caído'.",
                "Completar el .env del Hito 10 o config/conectividad.env (ver config/configuracion-ejemplo.env).",
                datos={"no_configurado": True},
            )
        return ok(detalle)

    cadena.ejecutar("configuracion", "variables", prueba, destino="(configuración)")
    if faltan and cadena.activa("configuracion"):
        cadena.bloquear("configuracion", f"no ejecutada: falta configuración ({', '.join(faltan)})")


def capa_contenedor(cadena: Cadena, cfg: Config, servicio: str) -> None:
    """Estado del contenedor y puertos publicados. Informativo: no prueba disponibilidad."""
    nombre = cfg.get("DOCKER_PREFIJO") + servicio

    def prueba() -> Paso:
        if Path("/.dockerenv").exists():
            return skip("diagnóstico ejecutado dentro de un contenedor: no se consulta el daemon de Docker")
        if not shutil.which("docker"):
            return skip("docker CLI no disponible en este entorno")
        formato = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.StartedAt}}"
        r = subprocess.run(
            ["docker", "inspect", "--format", formato, nombre],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if r.returncode != 0:
            return warn(
                f"no existe el contenedor '{nombre}'",
                "Puede ejecutarse con otro nombre o fuera de Docker.",
                "docker ps -a",
            )
        estado, salud, inicio = (r.stdout.strip().split("|") + ["", ""])[:3]
        puertos = subprocess.run(
            ["docker", "port", nombre], capture_output=True, text=True, timeout=10, check=False
        ).stdout.split("\n")
        publicados = ", ".join(sorted({p.strip() for p in puertos if p.strip() and "[::]" not in p})) or "ninguno"
        detalle = f"{nombre}: {estado}{f' ({salud})' if salud else ''}; puertos publicados: {publicados}"
        if estado != "running":
            return warn(
                detalle,
                "El contenedor no está en ejecución: explica las fallas de TCP de este producto.",
                f"docker start {nombre} (nunca 'down -v': se borrarían los volúmenes)",
            )
        return ok(f"{detalle}. Activo no implica disponible: lo deciden las capas siguientes", inicio=inicio)

    cadena.ejecutar("contenedor", "docker inspect", prueba, destino=nombre)


def clasificar_generico(exc: BaseException, capa: str) -> Paso:
    if isinstance(exc, LimiteExcedido):
        return fail(
            f"el cliente no respondió: {exc}",
            "El listener aceptó la conexión pero no completó el protocolo (puerto de otro producto, "
            "servidor iniciando o bloqueado).",
            "Verificar el puerto configurado y los logs del contenedor.",
        )
    return fail(
        resumen_excepcion(exc),
        f"Excepción no prevista en la capa '{capa}'.",
        "Revisar el detalle de la excepción y el log del producto.",
    )

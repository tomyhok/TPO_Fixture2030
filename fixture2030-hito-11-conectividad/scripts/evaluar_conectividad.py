"""Hito 11 - Evaluación de conectividad de la API integrada con sus productos NoSQL.

No crea, modifica ni borra datos de dominio. Recorre, por producto y de menor a
mayor costo: configuración -> resolución -> TCP -> protocolo -> autenticación ->
autorización -> contexto -> lectura mínima, y luego las rutas de la API.

Uso (desde fixture2030-hito-11-conectividad/):
    python scripts/evaluar_conectividad.py                       modo completo
    python scripts/evaluar_conectividad.py --modo tcp            configuración + DNS + TCP (sin drivers)
    python scripts/evaluar_conectividad.py --modo nativo         + clientes nativos y sondas
    python scripts/evaluar_conectividad.py --modo api            solo rutas de la API
    python scripts/evaluar_conectividad.py --producto redis,iris --capas protocolo,autenticacion
    python scripts/evaluar_conectividad.py --json salida.json --markdown salida.md

Estados: OK (esa prueba funcionó), WARN (funcionó con observación), FAIL (falló,
con hipótesis y siguiente paso), SKIP (no se ejecutó por falta de herramienta,
de configuración o porque falló una capa previa; NO significa "producto caído").
Código de salida: 0 siempre, salvo --estricto con algún FAIL (1).
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conectividad import api  # noqa: E402
from conectividad.config import RAIZ, Config  # noqa: E402
from conectividad.productos import PRODUCTOS  # noqa: E402
from conectividad.registro import (  # noqa: E402
    ABREVIATURA,
    CAPAS,
    FAIL,
    Redactor,
    Registro,
    ahora,
    matriz,
)

MODOS = {
    "config": {"configuracion"},
    "tcp": {"configuracion", "resolucion", "tcp", "contenedor"},
    "nativo": set(CAPAS) | {"contenedor", "portal_http", "sonda"},
    "api": set(),
    "completo": set(CAPAS) | {"contenedor", "portal_http", "sonda"},
}
DRIVERS = ("pymongo", "neo4j", "cassandra-driver", "redis", "intersystems-irispython")


def _commit() -> str:
    if not shutil.which("git"):
        return "no disponible (git no instalado)"
    try:
        corto = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        rama = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        sucio = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        return f"{corto} ({rama}{', con cambios sin commitear' if sucio else ''})"
    except (subprocess.SubprocessError, OSError):
        return "no disponible (fuera de un repositorio git)"


def _origen() -> str:
    """Desde dónde se ejecuta: localhost no significa lo mismo en la notebook y en un contenedor (RNF3)."""
    if Path("/.dockerenv").exists():
        return f"contenedor Docker ({platform.system()}); localhost = el propio contenedor"
    shell = "Git Bash" if os.environ.get("MSYSTEM") else ("PowerShell/cmd" if os.name == "nt" else "shell POSIX")
    return f"notebook {platform.system()} {platform.release()} ({shell}); 127.0.0.1 = puertos publicados por Docker"


def _versiones() -> str:
    partes = []
    for paquete in DRIVERS:
        try:
            partes.append(f"{paquete} {metadata.version(paquete)}")
        except metadata.PackageNotFoundError:
            partes.append(f"{paquete} (no instalado)")
    return ", ".join(partes)


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluación de conectividad del Fixture 2030 (Hito 11)")
    p.add_argument("--modo", choices=sorted(MODOS), default="completo")
    p.add_argument("--producto", default=",".join(PRODUCTOS),
                   help=f"lista separada por comas ({', '.join(PRODUCTOS)})")
    p.add_argument("--capas", help=f"limita las capas ({', '.join(CAPAS)}, contenedor, portal_http, sonda)")
    p.add_argument("--sin-sondas", action="store_true", help="omite las sondas negativas (inexistentes, errores)")
    p.add_argument("--etiqueta", default="", help="texto que identifica la corrida en la evidencia")
    p.add_argument("--json", type=Path, help="escribe resultados y matriz en JSON")
    p.add_argument("--markdown", type=Path, help="escribe la matriz y el detalle en Markdown")
    p.add_argument("--estricto", action="store_true", help="código de salida 1 si hay algún FAIL")
    return p.parse_args()


def _imprimir_matriz(registro: Registro, filas: list[dict[str, Any]]) -> None:
    columnas = [ABREVIATURA[c] for c in CAPAS]
    registro.escribir(f"{'producto':<10} {'estado':<15} " + " ".join(f"{c:<5}" for c in columnas)
                      + f" {'sondas':<6} {'API':<5} {'lect.ms':>8}")
    for f in filas:
        celdas = " ".join(f"{f['capas'][c]:<5}" for c in CAPAS)
        ms = f"{f['latencia_lectura_ms']:.1f}" if f["latencia_lectura_ms"] is not None else "-"
        registro.escribir(f"{f['producto']:<10} {f['estado']:<15} {celdas} {f['sondas']:<6} {f['api']:<5} {ms:>8}")
        registro.escribir(f"{'':<11}-> {f['diagnostico']}")


def _markdown(meta: dict[str, Any], registro: Registro, filas: list[dict[str, Any]],
              trazas: list[dict[str, Any]], logs: dict[str, list[str]]) -> str:
    r = registro.redactor
    md = [f"# Matriz de conectividad — {meta['etiqueta'] or meta['modo']}", ""]
    md += ["| Campo | Valor |", "|---|---|"]
    md += [f"| {k} | {r(str(v))} |" for k, v in meta.items() if k not in ("conteo",)]
    md += ["", "## Matriz por producto", ""]
    md += ["| Producto | Estado | " + " | ".join(ABREVIATURA[c] for c in CAPAS) + " | Sondas | API | Lectura (ms) | Diagnóstico |"]
    md += ["|---" * (len(CAPAS) + 6) + "|"]
    for f in filas:
        ms = f"{f['latencia_lectura_ms']:.1f}" if f["latencia_lectura_ms"] is not None else "-"
        md += [f"| {f['producto']} | **{f['estado']}** | " + " | ".join(f["capas"][c] for c in CAPAS)
               + f" | {f['sondas']} | {f['api']} | {ms} | {f['diagnostico'].replace('|', '/')} |"]
    md += ["", "## Resultados", "", "| Instante (UTC) | Producto | Capa | Prueba | Estado | ms | Destino | Detalle |",
           "|---|---|---|---|---|---|---|---|"]
    for x in registro.resultados:
        detalle = x.detalle + (f" — hipótesis: {x.hipotesis} — siguiente paso: {x.siguiente_paso}"
                               if x.estado == FAIL else "")
        md += [f"| {x.instante} | {x.producto} | {x.capa} | {x.prueba} | {x.estado} | "
               f"{x.duracion_ms if x.duracion_ms is not None else '-'} | `{x.destino}` | {detalle.replace('|', '/')} |"]
    if trazas:
        md += ["", "## Rutas de la API y log asociado", ""]
        for t in trazas:
            md += [f"- `{t['request_id']}` `GET {t['path']}` -> HTTP {t['status']} ({t['clase']})"]
            for linea in logs.get(t["request_id"], []):
                md += [f"  - `{r(linea)}`"]
    return "\n".join(md) + "\n"


def main() -> int:
    args = _argumentos()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252 por defecto
    cfg = Config()
    ocultables, publicos = cfg.secretos()
    registro = Registro(Redactor(ocultables), umbral_lento_ms=cfg.decimal("UMBRAL_LENTO_MS"))
    productos = [p.strip() for p in args.producto.split(",") if p.strip()]
    desconocidos = [p for p in productos if p not in PRODUCTOS]
    if desconocidos:
        print(f"Productos desconocidos: {desconocidos}. Usar: {', '.join(PRODUCTOS)}", file=sys.stderr)
        return 2
    capas = set(MODOS[args.modo])
    if args.capas:
        capas = {c.strip() for c in args.capas.split(",") if c.strip()}
    con_api = args.modo in ("api", "completo") and (not args.capas or "api" in capas)

    inicio = time.perf_counter()
    meta: dict[str, Any] = {
        "etiqueta": args.etiqueta,
        "inicio_utc": ahora(),
        "commit": _commit(),
        "origen": _origen(),
        "python": platform.python_version(),
        "drivers": _versiones(),
        "configuracion": ", ".join(cfg.archivos) or "solo valores por defecto",
        "modo": args.modo,
        "productos": ", ".join(productos),
        "capas": ", ".join(sorted(capas)) + (", api" if con_api else ""),
        "timeouts_s": f"tcp={cfg.get('TCP_TIMEOUT_S')} conexion={cfg.get('TIMEOUT_CONEXION_S')} "
                      f"operacion={cfg.get('TIMEOUT_OPERACION_S')} api={cfg.get('API_TIMEOUT_S')}",
    }
    registro.escribir("=" * 100)
    registro.escribir(f"Hito 11 — Evaluación de conectividad Fixture 2030{f' — {args.etiqueta}' if args.etiqueta else ''}")
    for clave, valor in meta.items():
        if clave != "etiqueta":
            registro.escribir(f"  {clave:<14} {valor}")
    if publicos:
        registro.escribir(f"  ADVERTENCIA    {publicos} secreto(s) coinciden con un identificador público de la "
                          "configuración (nombre de base, host...): no son secretos efectivos, conviene cambiarlos")
    registro.escribir("=" * 100)

    if capas:
        for nombre in productos:
            registro.escribir(f"\n--- {nombre} ---")
            try:
                PRODUCTOS[nombre].evaluar(cfg, registro, capas, sondas=not args.sin_sondas)
            except Exception as exc:  # noqa: BLE001 - un producto nunca corta la evaluación de los demás
                registro.escribir(f"[FAIL] {nombre}: error del diagnóstico ({type(exc).__name__}: {exc})")

    trazas: list[dict[str, Any]] = []
    logs: dict[str, list[str]] = {}
    if con_api:
        registro.escribir(f"\n--- API del Hito 10 ({cfg.get('API_URL')}) ---")
        trazas = api.evaluar(cfg, registro, productos)
        time.sleep(0.3)  # el log de la API se escribe de forma asíncrona respecto de la respuesta
        logs = api.lineas_de_log(cfg, [t["request_id"] for t in trazas])
        if logs:
            con_lineas = sum(1 for v in logs.values() if v)
            registro.escribir(f"  log asociado: {con_lineas}/{len(trazas)} requests encontradas en "
                              f"API_LOG_FILE={cfg.get('API_LOG_FILE')}")
        else:
            registro.escribir("  log asociado: no se encontró el log de la API (API_LOG_FILE); "
                              "la correlación queda en el header X-Request-ID")

    conteo = registro.conteo()
    filas = matriz(registro, productos)
    meta["fin_utc"] = ahora()
    meta["duracion_s"] = round(time.perf_counter() - inicio, 1)
    meta["conteo"] = conteo

    registro.escribir("\n" + "=" * 100)
    registro.escribir("Matriz de conectividad (OK | WARN | FAIL | SKIP | - = capa no ejecutada en este modo)")
    registro.escribir("=" * 100)
    _imprimir_matriz(registro, filas)
    registro.escribir("")
    registro.escribir(f"Total: {sum(conteo.values())} | OK: {conteo['OK']} | WARN: {conteo['WARN']} | "
                      f"FAIL: {conteo['FAIL']} | SKIP: {conteo['SKIP']} | duración {meta['duracion_s']} s")
    registro.escribir("Interpretación: OK indica que esa prueba concreta funcionó en este momento y desde este "
                      "origen; no garantiza rendimiento ni disponibilidad permanente. SKIP = prueba no ejecutada "
                      "(falta de herramienta, de configuración o capa previa fallida), no 'producto caído'.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        contenido = {"meta": meta, "matriz": filas, "resultados": registro.como_dict(),
                     "api": [{**t, "log": [registro.redactor(x) for x in logs.get(t["request_id"], [])]}
                             for t in trazas]}
        args.json.write_text(registro.redactor(json.dumps(contenido, ensure_ascii=False, indent=2)), encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(_markdown(meta, registro, filas, trazas, logs), encoding="utf-8")

    return 1 if args.estricto and conteo[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())


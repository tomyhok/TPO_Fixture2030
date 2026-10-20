"""Filtro de redacción para evidencias (RNF8): stdin -> stdout sin secretos.

Oculta los valores secretos configurados (contraseñas y token, leídos con la
misma configuración que el diagnóstico), URIs con credenciales, headers Bearer
y pares password=/token=. Conserva todo lo demás para que el diagnóstico siga
siendo interpretable.

Uso:  comando | python scripts/redactar.py > evidencia.txt
      python scripts/redactar.py --verificar docs/evidencia   (cuenta secretos presentes, sin mostrarlos)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conectividad.config import Config, es_secreta  # noqa: E402
from conectividad.registro import Redactor  # noqa: E402


def verificar(carpeta: Path) -> int:
    cfg = Config()
    publicos = [cfg.get(k) for k in cfg._valores if not es_secreta(k) and cfg.get(k)]  # noqa: SLF001
    candidatos = {k: cfg.get(k).strip() for k in cfg._valores if es_secreta(k)}  # noqa: SLF001
    token, origen = cfg.token_influx()
    candidatos[f"token InfluxDB ({origen})"] = token
    archivos = [a for a in carpeta.rglob("*") if a.is_file() and a.name != "verificacion_secretos.txt"]
    print(f"Archivos revisados: {len(archivos)} en {carpeta.name}/")
    problemas = 0
    for nombre, valor in candidatos.items():
        if not valor or valor == "<completar>":
            print(f"  {nombre:<45} sin valor configurado: nada que buscar")
            continue
        if any(valor in p for p in publicos):
            print(f"  {nombre:<45} NO VERIFICABLE por valor: coincide con un identificador público "
                  "(ver limitaciones: credencial igual a un identificador público)")
            continue
        apariciones = sum(a.read_text(encoding="utf-8", errors="replace").count(valor) for a in archivos)
        problemas += apariciones
        print(f"  {nombre:<45} {apariciones} apariciones")
    print("Resultado:", "sin secretos en la evidencia" if not problemas else f"{problemas} apariciones: REVISAR")
    return 1 if problemas else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "--verificar":
        return verificar(Path(sys.argv[2]))
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    ocultables, _ = Config().secretos()
    redactar = Redactor(ocultables)
    for linea in sys.stdin:
        sys.stdout.write(redactar(linea))
    return 0


if __name__ == "__main__":
    sys.exit(main())

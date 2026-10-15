"""Verifica la conectividad con las seis fuentes usando los mismos adaptadores que la API.

No necesita la API levantada: lee el .env, crea cada adaptador y ejecuta su
operación de ping con los timeouts configurados. Nunca imprime credenciales.

Uso (desde fixture2030-hito-10-api-integrada/):
    .venv/Scripts/python scripts/verificar_conectividad.py
Código de salida: 0 si las seis fuentes responden; 1 si alguna falla.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import obtener_settings  # noqa: E402
from app.core.errores import DependenciaTimeout, ErrorAPI  # noqa: E402
from app.core.observabilidad import configurar_logs  # noqa: E402
from app.dependencias import crear_adaptadores  # noqa: E402

DESTINOS = {
    "mongodb": lambda s: f"{s.mongo_host}:{s.mongo_port} db={s.mongo_database}",
    "neo4j": lambda s: f"{s.neo4j_uri} db={s.neo4j_database}",
    "cassandra": lambda s: f"{s.cassandra_hosts}:{s.cassandra_port} keyspace={s.cassandra_keyspace}",
    "redis": lambda s: f"{s.redis_host}:{s.redis_port} db={s.redis_db}",
    "influxdb": lambda s: f"{s.influx_url} database={s.influx_database}",
    "iris": lambda s: f"{s.iris_host}:{s.iris_port} namespace={s.iris_namespace}",
}


def main() -> int:
    settings = obtener_settings()
    configurar_logs("ERROR")  # solo la tabla de resultados
    adaptadores = crear_adaptadores(settings)
    print(f"Timeouts: conexion={settings.timeout_conexion_s}s operacion={settings.timeout_operacion_s}s\n")
    print(f"{'fuente':<10} {'estado':<8} {'ms':>8}  destino")
    fallas = 0
    try:
        for nombre, adaptador in adaptadores.como_dict().items():
            inicio = time.perf_counter()
            try:
                adaptador.ping()
                estado = "ok"
            except DependenciaTimeout:
                estado = "timeout"
            except ErrorAPI:
                estado = "caida"
            ms = (time.perf_counter() - inicio) * 1000
            fallas += estado != "ok"
            print(f"{nombre:<10} {estado:<8} {ms:>8.1f}  {DESTINOS[nombre](settings)}")
    finally:
        adaptadores.cerrar()
    print("\nResultado:", "todas las fuentes disponibles" if not fallas else f"{fallas} fuente(s) con problemas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())

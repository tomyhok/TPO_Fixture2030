"""Carga en InfluxDB las estadísticas de los partidos de muestra del Hito 10.

El generador del Hito 8 usa identificadores propios (M001 / EQ001_1). Para que
la API consulte el mismo partido en todas las fuentes, este script escribe en la
misma tabla `estadisticas_partido` (mismo modelo: tags partido_id y equipo_id,
mismos fields) los partidos P-001 (ARG vs ESP) y P-002 (URU vs ARG), con un
punto por segundo durante 2 horas. No borra ni modifica los datos del Hito 8.

Es idempotente: la semilla aleatoria es fija y un punto con la misma serie y el
mismo timestamp reemplaza al anterior.

Uso (desde fixture2030-hito-10-api-integrada/, con el .env configurado):
    .venv/Scripts/python scripts/datos/cargar_estadisticas_influx.py
"""

import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.config.settings import obtener_settings  # noqa: E402

PARTIDOS = [
    # codigo, local, visitante, inicio (UTC)
    ("P-001", "ARG", "ESP", datetime(2030, 6, 10, 20, 0, tzinfo=UTC)),
    ("P-002", "URU", "ARG", datetime(2030, 6, 12, 20, 0, tzinfo=UTC)),
]
DURACION_S = 2 * 60 * 60
LOTE = 10_000


def lineas_partido(codigo: str, local: str, visitante: str, inicio: datetime) -> list[str]:
    rnd = random.Random(codigo)
    posesion_local = 50.0
    acumulados = {local: [0, 0], visitante: [0, 0]}  # pases, tiros
    usuarios = {local: rnd.randint(150_000, 300_000), visitante: rnd.randint(80_000, 200_000)}
    base = int(inicio.timestamp())
    lineas = []
    for segundo in range(DURACION_S):
        posesion_local = max(25.0, min(75.0, posesion_local + rnd.uniform(-0.6, 0.6)))
        # En el dato real la posesión de los dos equipos suma 100 en cada instante.
        posesiones = {local: posesion_local, visitante: 100.0 - posesion_local}
        for equipo in (local, visitante):
            acumulados[equipo][0] += rnd.choices([0, 1, 2], weights=[55, 35, 10])[0]
            acumulados[equipo][1] += rnd.choices([0, 1], weights=[997, 3])[0]
            usuarios[equipo] = max(1_000, usuarios[equipo] + rnd.randint(-800, 900))
            pases, tiros = acumulados[equipo]
            lineas.append(
                f"estadisticas_partido,partido_id={codigo},equipo_id={equipo} "
                f"posesion_pct={posesiones[equipo]:.2f},pases_completados={pases}i,"
                f"tiros={tiros}i,usuarios_activos={usuarios[equipo]}i {base + segundo}"
            )
    return lineas


def main() -> int:
    settings = obtener_settings()
    token = settings.token_influx()
    if not token:
        print("No hay token de InfluxDB: definir INFLUX_TOKEN o ejecutar fixture2030-influxDB/scripts/inicializacion.sh")
        return 1
    with httpx.Client(base_url=settings.influx_url, timeout=30) as cliente:
        for codigo, local, visitante, inicio in PARTIDOS:
            lineas = lineas_partido(codigo, local, visitante, inicio)
            for i in range(0, len(lineas), LOTE):
                r = cliente.post(
                    "/api/v3/write_lp",
                    params={"db": settings.influx_database, "precision": "second"},
                    content="\n".join(lineas[i : i + LOTE]),
                    headers={"Authorization": f"Bearer {token}"},
                )
                if r.status_code not in (200, 204):
                    print(f"Error al escribir {codigo}: HTTP {r.status_code}")
                    return 1
            print(f"{codigo}: {len(lineas)} puntos ({local} vs {visitante}, desde {inicio.isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

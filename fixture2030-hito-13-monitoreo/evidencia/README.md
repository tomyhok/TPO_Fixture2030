# Evidencia del Hito 13 — qué está observado y qué no (RNF2, RNF8)

Esta carpeta separa la evidencia **observada** (salida real de Prometheus, Grafana y Docker) de las **simulaciones** y de las **maquetas**. Nada de lo que está en `simulacion_sin_docker/` ni en la maqueta SVG puede presentarse como medición.

La corrida observada se hizo el **2026-11-23** (20:38–20:58 UTC) con las 6 bases, la API integrada del Hito 10 en `0.0.0.0:8000` y el stack de monitoreo levantados. La línea de tiempo y la interpretación de cada panel están en [`dashboards/README.md`](dashboards/README.md).

| Archivo / carpeta | Tipo | Cómo se genera | Estado |
|---|---|---|---|
| [`prometheus_targets.json`](prometheus_targets.json) / [`.txt`](prometheus_targets.txt) / [`_2026-11-23.jpeg`](prometheus_targets_2026-11-23.jpeg) | **Observado** | `scripts/verificar_targets.ps1` (o `.sh`) con el stack levantado | 2026-11-23 19:57 UTC: 3 targets `UP`, 6 bases `fixture_db_up = 1`, 4 reglas cargadas |
| [`prueba_de_falla.json`](prueba_de_falla.json) / [`.md`](prueba_de_falla.md) | **Observado** | `scripts/ejecutar_prueba_controlada.ps1 --espera-scrape 30` | 2026-11-23 20:44–20:47 UTC: Redis `1 → 0 → 1`, alerta `firing`, aislamiento OK; ruta Redis respondió **504** en vez de 503 (explicado en `dashboards/README.md`) |
| [`dashboards/capturas/`](dashboards/capturas/) | **Observado** | Capturas de Grafana tras la recuperación (rango *Last 15 minutes*, sin credenciales visibles) | 4 capturas, una por fila del dashboard |
| [`dashboards/grafana_csv/`](dashboards/grafana_csv/) | **Observado** | Grafana → *Inspect → Data* (*Series joined by time*, sin formato) | 8 CSV, uno por panel |
| [`dashboards/datos_paneles_20261123T203800Z.*`](dashboards/) | **Observado** | `python scripts/exportar_datos_dashboard.py --desde ... --hasta ...` (Prometheus `query_range`) | 63 series de los 8 paneles, 20:38–20:49 UTC |
| [`dashboards/vista_dashboard_war_room.svg`](dashboards/vista_dashboard_war_room.svg) | **Maqueta** | Dibujada a mano para mostrar la disposición de los paneles | No es una captura |
| [`simulacion_sin_docker/`](simulacion_sin_docker/) | **Simulación** | `python scripts/generar_evidencia_y_validar.py` (sin Docker) | Valores sintéticos procesados por el colector real `metricas.py` |
| [`resultados_sin_secretos/verificacion_secretos.txt`](resultados_sin_secretos/verificacion_secretos.txt) | Verificación | `python scripts/generar_evidencia_y_validar.py` | Escaneo de secretos del Hito 13 |

## Cómo repetir la evidencia observada

Con las 6 bases, la API (`0.0.0.0:8000`) y el stack de monitoreo levantados (ver el [README](../README.md)):

```bash
bash scripts/verificar_targets.sh                              # evidencia/prometheus_targets.*
bash scripts/ejecutar_prueba_controlada.sh --espera-scrape 30  # evidencia/prueba_de_falla.*
python scripts/exportar_datos_dashboard.py --desde <inicio UTC> --hasta <fin UTC>   # evidencia/dashboards/datos_paneles_*
```

Notas de la corrida:

- **Tráfico de fondo:** para que los paneles de latencia y throughput tengan datos, durante la corrida se generó tráfico **solo de lectura** (GET secuenciales a las 6 rutas de muestra, ~2 req/s por ruta) durante 20 minutos. No modifica datos funcionales (RNF5).
- **Sesiones de Redis:** las sesiones de muestra `S-0001..S-0010` tienen TTL de 1800 s. Si vencieron, `/sesiones/S-0001` responde 404; se recargan sin tocar otras bases con
  `docker exec fixture2030-redis sh -c "grep -v '^#' /scripts/carga_muestra.redis | redis-cli"`.
- El `.md` de la prueba incluye una tabla de verificaciones calculada sobre los datos observados: si algo no se cumplió, aparece como **No** y se explica, no se corrige a mano.
- Los timestamps de cada fase en `prueba_de_falla.json` difieren (hay esperas de scraping entre fases); eso permite verificar que la corrida fue real.

# Evidencia del Hito 13 — qué está observado y qué no (RNF2, RNF8)

Esta carpeta separa la evidencia **observada** (salida real de Prometheus, Grafana y Docker) de las **simulaciones** y de las **maquetas**. Nada de lo que está en `simulacion_sin_docker/` ni en la maqueta SVG puede presentarse como medición.

| Archivo / carpeta | Tipo | Cómo se genera | Estado |
|---|---|---|---|
| `prometheus_targets.json` / `.txt` | **Observado** | `python scripts/verificar_targets.py --guardar` con el stack levantado | **Pendiente**: correr con Docker |
| `prueba_de_falla.json` / `.md` | **Observado** | `bash scripts/ejecutar_prueba_controlada.sh` (o `.ps1`) con el stack levantado | **Pendiente**: correr con Docker |
| `dashboards/*.png` | **Observado** | Captura de pantalla de Grafana durante la prueba de falla (sin credenciales visibles) | **Pendiente** |
| `dashboards/vista_dashboard_war_room.svg` | **Maqueta** | Dibujada a mano para mostrar la disposición de los paneles | No es una captura |
| `simulacion_sin_docker/` | **Simulación** | `python scripts/generar_evidencia_y_validar.py` (sin Docker) | Valores sintéticos procesados por el colector real `metricas.py` |
| `resultados_sin_secretos/verificacion_secretos.txt` | Verificación | `python scripts/generar_evidencia_y_validar.py` | Escaneo de secretos del Hito 13 |

## Cómo completar la evidencia observada

Con las 6 bases, la API (`0.0.0.0:8000`) y el stack de monitoreo levantados (ver el [README](../README.md)):

```bash
bash scripts/verificar_targets.sh            # escribe evidencia/prometheus_targets.*
bash scripts/ejecutar_prueba_controlada.sh   # escribe evidencia/prueba_de_falla.*
```

Mientras corre la prueba de falla, conviene capturar el dashboard de Grafana (rango `Last 15 minutes`) y guardar la imagen en `dashboards/` con la fecha en el nombre. El `.md` de la prueba incluye una tabla de verificaciones calculada sobre los datos observados: si algo no se cumplió (por ejemplo, la alerta quedó en `pending`), aparece como **No** y debe explicarse, no corregirse a mano.

Los timestamps de cada fase en `prueba_de_falla.json` deben diferir (hay esperas de scraping entre fases); eso permite verificar que la corrida fue real.

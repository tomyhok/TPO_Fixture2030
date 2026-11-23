# Evidencia de Prueba Controlada y Reversible (RF10, RNF11)

- **Fecha UTC:** `2026-11-23T20:44:46Z`
- **Modo de ejecución:** `docker_y_prometheus_en_vivo`
- **Componente intervenido:** `redis` (contenedor `fixture2030-redis`)
- **Intervalo de espera de scraping:** `30s`

## 1. Comparación de las Tres Fases en Prometheus

| Métrica / Indicador | Fase 1: Antes de la Falla | Fase 2: Durante `docker stop` | Fase 3: Tras `docker start` |
|---|---|---|---|
| Estado general API (`/health/dependencias`) | `up` | `degraded` | `up` |
| `fixture_db_up{db="redis"}` | `1` | **`0`** | `1` |
| `fixture_db_up{db="mongodb"}` (aislamiento) | `1` | `1` | `1` |

## 2. Solicitudes HTTP Ejecutadas Durante la Falla (Fase 2)

| Motor | Ruta | Código HTTP | Latencia (ms) |
|---|---|---:|---:|
| `redis` | `/sesiones/S-0001` | `504` | `4042.2` |
| `mongodb` | `/equipos/ARG` | `200` | `2031.2` |
| `redis` | `/sesiones/S-0001` | `504` | `4047.2` |
| `mongodb` | `/equipos/ARG` | `200` | `2037.4` |
| `redis` | `/sesiones/S-0001` | `504` | `4022.3` |
| `mongodb` | `/equipos/ARG` | `200` | `2066.2` |

## 3. Alertas en Prometheus por fase

| Fase | Alertas no inactivas |
|---|---|
| 1 | ninguna |
| 2 | BaseDatosNoSQLNoDisponible (firing), LatenciaAPISuperaSLA100ms (pending), ErroresDependenciaSostenidos (firing) |
| 3 | LatenciaAPISuperaSLA100ms (firing), ErroresDependenciaSostenidos (firing) |

## 4. Verificaciones (calculadas sobre los datos observados)

| Verificación | Resultado | Observado |
|---|---|---|
| Detección: `fixture_db_up{db="redis"}` pasa de 1 a 0 | Sí | `1` → `0` |
| Alerta `BaseDatosNoSQLNoDisponible` en `firing` durante la falla | Sí | `firing` |
| Ruta de `redis` responde 503 | **No** | `[504, 504, 504]` |
| Aislamiento: ruta de otra base sigue en 200 | Sí | `[200, 200, 200]` |
| Recuperación: `fixture_db_up` vuelve a 1 tras `docker start` | Sí | `1` |

La prueba solo usa `docker stop`/`docker start` sobre un contenedor de laboratorio: no borra volúmenes ni modifica datos (RNF11).

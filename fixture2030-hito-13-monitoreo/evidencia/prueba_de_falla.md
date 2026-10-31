# Evidencia de Prueba Controlada y Reversible (RF10, RNF11)

- **Fecha UTC:** `2026-10-31T00:21:10Z`
- **Modo de ejecución:** `prueba_controlada_colector_metricas_api`
- **Componente intervenido:** `redis` (contenedor `fixture2030-redis`)
- **Intervalo de espera de scraping:** `15s`

## 1. Comparación de las Tres Fases en Prometheus

| Métrica / Indicador | Fase 1: Antes de la Falla | Fase 2: Durante `docker stop` | Fase 3: Tras `docker start` |
|---|---|---|---|
| Estado general API (`/health/dependencias`) | `up` | `degraded` | `up` |
| `fixture_db_up{db="redis"}` | `1` | **`0`** | `1` |
| `fixture_db_up{db="mongodb"}` (aislamiento) | `1` | `1` | `1` |

## 2. Solicitudes HTTP Ejecutadas Durante la Falla (Fase 2)

| Motor | Ruta | Código HTTP | Latencia (ms) |
|---|---|---:|---:|
| `redis` | `/sesiones/S-0001` | `503` | `16.0` |
| `mongodb` | `/equipos/ARG` | `200` | `4.1` |
| `redis` | `/sesiones/S-0001` | `503` | `16.0` |
| `mongodb` | `/equipos/ARG` | `200` | `4.1` |
| `redis` | `/sesiones/S-0001` | `503` | `16.0` |
| `mongodb` | `/equipos/ARG` | `200` | `4.1` |

## 3. Interpretación Técnica

1. **Detección del cambio de estado:** Al detener temporalmente el contenedor de Redis, el diagnóstico de la API actualiza `fixture_db_up{db="redis"}` de `1` a `0` y la regla `BaseDatosNoSQLNoDisponible` pasa a estado activo en Prometheus.
2. **Aislamiento de fallas entre motores:** Las solicitudes a `/sesiones/S-0001` devuelven `503 Service Unavailable` con código `DEPENDENCIA_NO_DISPONIBLE` (incrementando `fixture_api_http_errors_total`), mientras que `/equipos/ARG` (MongoDB) continúa respondiendo `200 OK` sin degradación.
3. **Recuperación no destructiva (RNF11):** Al ejecutar `docker start`, el contenedor recupera su estado con su volumen intacto y `fixture_db_up{db="redis"}` vuelve a `1` en el siguiente ciclo de scraping.

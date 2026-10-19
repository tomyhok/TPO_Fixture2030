# Health, readiness y diagnóstico por dependencia (sección 5.6)

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Implementado en la API del Hito 10 (versión 1.1.0):
[`app/routes/salud.py`](../../fixture2030-hito-10-api-integrada/app/routes/salud.py),
[`app/services/salud_service.py`](../../fixture2030-hito-10-api-integrada/app/services/salud_service.py)
y [`app/schemas/salud.py`](../../fixture2030-hito-10-api-integrada/app/schemas/salud.py).
Pruebas: [`tests/unit/test_salud.py`](../../fixture2030-hito-10-api-integrada/tests/unit/test_salud.py) (10 pruebas).
El contrato está en `openapi/openapi.yaml`.

## 1. Endpoints

| Endpoint | Pregunta | ¿Consulta bases? | Respuesta |
|---|---|---|---|
| `GET /health/live` | ¿El proceso de la API está vivo? | **No** | Siempre 200 `{"estado":"up","version":"1.1.0","activa_desde_s":…}`. Si el proceso está colgado o detenido, no hay respuesta: esa es la señal |
| `GET /health/ready` | ¿La API puede recibir tráfico? | Sí, con el diagnóstico reutilizado (TTL) | 200 si **al menos una** fuente está disponible; 503 si ninguna. Incluye `disponibles` y `no_disponibles` |
| `GET /health/dependencias` | ¿Cómo está cada fuente? | Sí, reutilizado (TTL), o fresco con `?refrescar=true` | 200 con el estado de cada fuente: el recurso pedido es el informe |
| `GET /health` (Hito 10, sin cambios) | ¿Responden las seis fuentes ahora? | Sí, **en cada llamada** | 200 si las seis responden; 503 si alguna falla, indicando cuál |

Ninguna ruta de negocio consulta las seis bases: cada ruta usa solo la fuente
de su módulo. El chequeo profundo solo corre cuando alguien llama a
`/health/ready`, `/health/dependencias` o `/health`.

### Política de readiness

La API es modular: cada ruta depende de una fuente propia. Si readiness
respondiera 503 porque cayó **una** fuente, un balanceador sacaría de servicio
la API completa y cortaría también los módulos sanos. Por eso:

* `listo=true` (200) mientras haya al menos una fuente `up` o `degraded`. Las rutas de la fuente caída responden 503/504 con la dependencia identificada, y `no_disponibles` la lista.
* `listo=false` (503) cuando ninguna fuente está disponible (evidencia B1: `estado=down`, las seis en `no_disponibles`).

## 2. Estados (significado fijo)

| Estado | Por fuente | Global |
|---|---|---|
| `up` | El ping configurado terminó bien, dentro de `HEALTH_UMBRAL_LENTO_MS` | Todas las fuentes `up` |
| `down` | Se intentó y falló: caída, rechazo, credencial, contexto inexistente (`motivo=DEPENDENCIA_NO_DISPONIBLE`) o timeout (`motivo=DEPENDENCIA_TIMEOUT`) | Ninguna fuente disponible |
| `degraded` | Respondió, pero más lento que `HEALTH_UMBRAL_LENTO_MS` (`motivo=LATENCIA_ALTA`) | Alguna fuente no está `up` |
| `unknown` | No se pudo evaluar: el chequeo lanzó un error inesperado (`motivo=ERROR_INESPERADO`, traza solo en el log) | — |
| `not_configured` | Faltan variables imprescindibles: **no se consulta** (`motivo=FALTA_CONFIGURACION:IRIS_PASSWORD`, solo el nombre de la variable) | — |

El ping de cada adaptador verifica también el **contexto**. MongoDB comprueba
que existan `equipos` y `jugadores` en la database configurada; Neo4j,
Cassandra, InfluxDB e IRIS ejecutan su ping dentro de la database, keyspace o
namespace configurado. Así, un contexto inexistente aparece como `down` y no
como `up`.

Ejemplo real con MongoDB detenido (`fallo_controlado_mongodb.txt`):

```json
{"estado":"degraded","verificado_en":"2026-10-17T00:33:40.648235Z","desde_cache":false,"edad_s":0.0,"ttl_cache_s":10.0,
 "dependencias":[{"nombre":"mongodb","estado":"down","motivo":"DEPENDENCIA_NO_DISPONIBLE","latencia_ms":2305.4},
                 {"nombre":"neo4j","estado":"up","motivo":null,"latencia_ms":6.9},
                 {"nombre":"cassandra","estado":"up","motivo":null,"latencia_ms":7.1}, …]}
```

## 3. Frecuencia, timeout y costo del chequeo profundo

| Aspecto | Valor |
|---|---|
| Frecuencia máxima | Una evaluación cada `HEALTH_CACHE_TTL_S` (**10 s**) por proceso, sin importar cuántos clientes consulten `/health/ready` o `/health/dependencias`. Un lock evita evaluaciones simultáneas: las llamadas concurrentes esperan y reciben el mismo resultado |
| Forzar | `GET /health/dependencias?refrescar=true` (diagnóstico manual) |
| Timeout | El de cada adaptador: conexión 2 s + operación 5 s. Las seis fuentes se consultan **en paralelo**, así que el peor caso es ~7 s (IRIS, límite por hilo). Medido con las seis caídas: 2,1 s |
| Costo con todo `up` | 6 operaciones triviales en paralelo; 15–45 ms en total (`resultados_api.txt`): `listCollections` filtrado, `RETURN 1`, `SELECT release_version FROM system.local`, `PING`, `SELECT 1`, `%SYSTEM.Version.GetNumber` |
| Costo por sondeo con caché | 0 consultas a las bases; 1–2 ms en el servidor (log: `ruta=/health/ready estado=200 duracion_ms=1.3`); 19 ms cuando le toca refrescar |
| Configuración | `HEALTH_CACHE_TTL_S` (0 = sin caché) y `HEALTH_UMBRAL_LENTO_MS` (1000) en el `.env` de la API |

Compromisos observados:

* **Retraso de hasta un TTL.** Tras recuperar MongoDB, readiness informó `degraded` durante unos segundos porque reutilizaba el chequeo anterior; `?refrescar=true` ya mostraba `up` (evidencia del fallo controlado, paso 5). Con 10 s de TTL, un balanceador tarda como máximo 10 s más en ver el cambio.
* **El primer chequeo incluye conexiones perezosas.** Justo después de arrancar, Cassandra dio `degraded/LATENCIA_ALTA` (1436 ms) por la apertura de la sesión del driver; el chequeo siguiente dio 9 ms. Es real: la primera request de comentarios también paga ese costo. Para el Hito 12 conviene un precalentamiento al iniciar la API.

## 4. Cómo lo usa el diagnóstico del Hito 11

`scripts/prueba_api.sh` llama a `/health/live`, `/health/ready` y
`/health/dependencias?refrescar=true`. Si el diagnóstico de la API informa una
fuente que no está `up`, la prueba queda en WARN y la columna API de esa fuente
en la matriz deja de estar en OK. La comparación entre esa columna y las capas
nativas distingue "producto caído" de "la API no lo puede usar" (estado
**degradado** en la matriz).

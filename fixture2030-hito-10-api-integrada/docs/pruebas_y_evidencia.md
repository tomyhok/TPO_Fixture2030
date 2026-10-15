# Hito 10 — Pruebas, Evidencia y Rendimiento Básico

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Pruebas** y **Rendimiento básico** de la
sección 8 del enunciado y las secciones 5.12 (RF14, RF15, RF17, RNF18).

---

## 1. Método elegido

| Herramienta | Para qué | Cómo se ejecuta |
|---|---|---|
| **pytest** (framework de tests) | Pruebas automáticas unitarias y de integración | `bash scripts/ejecutar_pruebas.sh` (o `.ps1`) |
| **cURL** | Escenarios reproducibles con request y respuesta completas, guardados como evidencia | `bash scripts/generar_evidencia.sh --con-caida` |
| **Swagger UI** | Exploración y prueba manual de cada ruta con los ejemplos del contrato | `http://127.0.0.1:8000/docs` |
| **Postman / Newman** | Colección de 64 requests con 264 aserciones: rutas principales y escenarios de error de los 16 casos | Importar `postman/` en Postman y usar el Runner, o `bash scripts/ejecutar_postman.sh` (ver [`postman/README.md`](../postman/README.md)) |

Ninguna prueba necesita escribir credenciales: las de integración leen el
`.env` local y la salida no las muestra.

## 2. Pruebas automáticas (157)

### Unitarias — `tests/unit/` (122, sin bases)

Usan la aplicación real (rutas, servicios, validación, manejo de errores,
OpenAPI) con **dobles en memoria** de los seis adaptadores
(`tests/unit/dobles.py`). Los dobles registran cada llamada y pueden simular
una falla.

| Archivo | Pruebas | Qué demuestra |
|---|---:|---|
| `test_validacion.py` | 41 | Parámetros de ruta, query, headers y cuerpos inválidos → 400 **sin ninguna llamada a una fuente** (RNF3) |
| `test_casos_de_uso.py` | 21 | Éxito, ausencia (404), vacío válido (200 `[]`), caché MISS/HIT, transiciones y conflictos (409) de los 16 casos |
| `test_errores.py` | 19 | Fuente no disponible (503) y timeout (504) en cada uno de los 6 módulos, respuesta degradada `BYPASS`, error interno sin detalle, request ID, 404/405 |
| `test_idempotencia.py` | 8 | Reintento con la misma clave sin duplicar, clave con otro cuerpo, clave en curso, liberación ante fallas, Redis caído |
| `test_adaptadores.py` | 28 | Traducción de las excepciones reales de cada driver a 503/504; los errores de programación no se disfrazan de 503; Cypher y SQL solo con parámetros |
| `test_contrato_openapi.py` | 5 | `openapi.yaml` igual a la API, rutas = casos de uso, sin 422, errores con el esquema común |

### Integración — `tests/integration/` (35, con las seis bases)

Usan la API real contra las fuentes reales (`TestClient` con los adaptadores
reales y el `.env`). Cada respuesta se contrasta con el contrato OpenAPI
(`documentado()`: el código devuelto debe estar declarado para esa operación).

| Archivo | Pruebas | Qué demuestra |
|---|---:|---|
| `test_api_integracion.py` | 24 | Un caso válido por módulo y además: paginación completa de las 64 selecciones sin repetidos, cursor de Cassandra sin solapamiento, caché con TTL real, partido inexistente vs. sin eventos, sesión que expira de verdad (TTL 1 s), cierre idempotente, posesión que suma 100 y contadores monótonos en InfluxDB, tope de puntos, ciclo de vida completo del acta en IRIS (409, idempotencia, `%OnBeforeSave`) |
| `test_dependencias_caidas.py` | 11 | API apuntada a un puerto sin servicio: las 6 rutas responden 503/504 en menos de 10 s, `/health` 503, no se escribe sin Redis. Servidor que acepta y no responde (dependencia lenta): Redis, InfluxDB y MongoDB cortan por timeout en menos de 5 s |

### Cobertura de la sección 5.12

| Requisito | Dónde |
|---|---|
| Una request válida por módulo | `TestMongoDB`, `TestNeo4j`, `TestCassandra`, `TestRedis`, `TestInfluxDB`, `TestIRIS` · evidencia 02–07 |
| Parámetro inválido | `test_validacion.py` · evidencia 08 |
| Recurso inexistente | `test_seleccion_inexistente`, `test_partido_inexistente`, `test_acta_y_acta_inexistente` · evidencia 02, 03, 07 |
| Respuesta vacía válida | `test_eventos_inexistente_vs_sin_eventos`, `test_ventana_sin_comentarios`, `test_ventana_sin_puntos`, `test_pagina_fuera_de_rango_es_vacia` |
| Sesión ausente o expirada | `test_sesion_expirada` · evidencia 05 |
| Dependencia detenida o inaccesible | `test_dependencias_caidas.py` · evidencia 09 (Redis detenido con `docker stop`) |
| Escritura repetida | `test_publicar_y_repetir_no_duplica`, `test_ciclo_de_vida_del_acta`, `test_idempotencia.py` · evidencia 04, 07 |
| Límites, paginación, ventanas | `test_paginacion_ordenada_por_ranking`, `test_muro_paginado_con_cursor`, `test_limite_de_puntos`, `test_intervalo_invertido` |
| Documentación y respuesta real compatibles | `test_contrato_openapi.py`, `documentado()` en cada prueba de integración · evidencia 13 |

## 3. Evidencia (RF17)

`docs/evidencia/` se genera con `bash scripts/generar_evidencia.sh --con-caida`
con la API levantada. Cada archivo indica fecha, comando y origen. Ninguno
contiene credenciales. El índice está en [`evidencia/README.md`](evidencia/README.md).

## 4. Rendimiento básico (RNF18)

Resultado completo: [`evidencia/12_latencia.md`](evidencia/12_latencia.md),
generado con `scripts/medir_latencia.py`.

* **Método:** 200 requests HTTP secuenciales por escenario, con un cliente,
  después de 10 de calentamiento. Latencia medida en el cliente (incluye
  HTTP local, API y fuente).
* **Entorno:** Windows 11, 16 CPU lógicas, Python 3.12, Docker Desktop
  (Engine 29.7.2). API con uvicorn de 1 worker en la notebook y las seis bases
  en contenedores de la misma máquina.
* **Volumen:** 64 selecciones, 1.472 jugadores, grafo del Hito 5, muestra de
  comentarios del Hito 6, 28.800 puntos de P-001/P-002 en InfluxDB más el
  millón del Hito 8 (si se cargó), 3 actas en IRIS.

Resultados observados (p50 / p95, ms): lecturas por clave en MongoDB, Redis
e IRIS ≈ 2–3 / 4–6. Ficha del partido desde caché ≈ 4 / 7. Eventos en Neo4j
≈ 10 / 18. Muro de Cassandra (4 particiones) ≈ 16 / 18. InfluxDB con ventana
de 30 min a 1m ≈ 15 / 18 y con ventana de 3 h a 10s ≈ 35 / 45. Una validación
rechazada responde en ≈ 1 ms porque no consulta ninguna base.

**Limitaciones:** no se midió concurrencia ni throughput; todas las bases
comparten la CPU y la memoria con la API; cada base es un nodo único sin
réplicas; los volúmenes son de laboratorio. Las cifras sirven para comparar
escenarios en este entorno, no para dimensionar producción (ver la pregunta
guía 20 en [`preguntas_guia.md`](preguntas_guia.md)).

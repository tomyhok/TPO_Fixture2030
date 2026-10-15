# Hito 10 — Contratos, Validación, Errores e Idempotencia

Grupo 4 — Ingeniería de Datos II — Fixture 2030

Este documento cubre los apartados **Mapa de endpoints**, **Contratos**,
**Validación**, **Errores** e **Idempotencia** de la sección 8 del enunciado
(RF11–RF13, RF19, RNF2–RNF4, RNF12, RNF14).

---

## 1. Contrato OpenAPI

* **Archivo versionado:** [`openapi/openapi.yaml`](../openapi/openapi.yaml), OpenAPI 3.1.
* **Swagger UI:** `http://localhost:8000/docs`. **JSON servido:** `http://localhost:8000/openapi.json`.
* **Cómo se mantiene alineado (RNF2):** el contrato no se escribe a mano. Se
  genera del código con `python scripts/exportar_openapi.py` (rutas,
  validaciones y schemas Pydantic). La prueba
  `tests/unit/test_contrato_openapi.py` falla si el archivo versionado difiere
  de la aplicación, si aparece una ruta que no está en los casos de uso o si
  se documenta un código que la API no produce (por ejemplo, el 422 que
  FastAPI agrega por defecto y que esta API reemplaza por 400). Las pruebas de
  integración verifican además que cada respuesta real use un código
  declarado para esa operación (`documentado()` en `tests/integration/`).
* **Contenido mínimo de la sección 5.4:** título y versión, servidor local,
  7 tags por módulo, rutas y métodos, parámetros con patrón/rango/enum,
  cuerpos con ejemplo, schemas de respuesta, códigos posibles por operación,
  esquema de error `ErrorRespuesta` con ejemplos. No hay autenticación en este
  hito, y así se declara en la descripción del contrato.

## 2. Mapa de endpoints

| Método | Ruta | Fuente | Operación | CU | Éxito | Errores posibles |
|---|---|---|---|---|---|---|
| GET | `/equipos` | MongoDB | Lectura paginada | CU02 | 200 | 400, 500, 503, 504 |
| GET | `/equipos/{codigo_iso}` | MongoDB | Lectura | CU01 | 200 | 400, 404, 500, 503, 504 |
| GET | `/equipos/{codigo_iso}/jugadores` | MongoDB | Lectura paginada | CU03 | 200 | 400, 404, 500, 503, 504 |
| GET | `/jugadores/{id_jugador}` | MongoDB | Lectura | CU04 | 200 | 400, 404, 500, 503, 504 |
| GET | `/partidos/{codigo_partido}` | Redis + Neo4j | Lectura con caché | CU05 | 200 (`X-Cache`) | 400, 404, 500, 503, 504 |
| GET | `/partidos/{codigo_partido}/eventos` | Neo4j | Lectura limitada | CU06 | 200 | 400, 404, 500, 503, 504 |
| GET | `/equipos/{codigo_iso}/rivales` | Neo4j | Lectura limitada | CU07 | 200 | 400, 404, 500, 503, 504 |
| GET | `/partidos/{codigo_partido}/comentarios` | Cassandra | Lectura por partición con cursor | CU08 | 200 | 400, 500, 503, 504 |
| POST | `/partidos/{codigo_partido}/comentarios` | Redis + Neo4j + Cassandra | Creación idempotente | CU09 | 201 / 200 repetida | 400, 404, 409, 500, 503, 504 |
| GET | `/sesiones/{id_sesion}` | Redis | Lectura | CU10 | 200 | 400, 404, 500, 503, 504 |
| DELETE | `/sesiones/{id_sesion}` | Redis | Invalidación | CU11 | 204 | 400, 500, 503, 504 |
| GET | `/partidos/{codigo_partido}/estadisticas` | InfluxDB | Ventana temporal agregada | CU12 | 200 | 400, 500, 503, 504 |
| GET | `/partidos-oficiales/{codigo_partido}` | IRIS | Lectura de objetos | CU13 | 200 | 400, 404, 500, 503, 504 |
| PATCH | `/partidos-oficiales/{codigo_partido}/estado` | IRIS | Actualización validada | CU14 | 200 | 400, 404, 409, 500, 503, 504 |
| POST | `/partidos-oficiales/{codigo_partido}/eventos` | Redis + IRIS | Creación validada e idempotente | CU15 | 201 / 200 repetida | 400, 404, 409, 500, 503, 504 |
| GET | `/health` | Las seis | Chequeo de conectividad | CU16 | 200 | 503 |

Cualquier ruta inexistente responde 404 y un método no soportado responde 405,
los dos con el formato de error común.

## 3. Validación (RF10, RNF3)

La validación ocurre **antes** de llamar a cualquier adaptador. Las pruebas
`tests/unit/test_validacion.py` verifican que una entrada inválida no produce
ninguna llamada a ninguna fuente.

| Elemento | Regla | Dónde |
|---|---|---|
| `codigo_iso` | `^[A-Z]{3}$` | ruta (`routes/parametros.py`) |
| `id_jugador` | `^[A-Z]{3}-\d{1,2}$` | ruta |
| `codigo_partido` | `^P-\d{3}$` | ruta |
| `id_sesion` | `^S-\d{4,}$` | ruta |
| `confederacion`, `grupo`, `posicion`, `resolucion`, `estado`, `tipo`, `idioma` | enums cerrados | query / cuerpo (Pydantic) |
| `page` / `size` / `limit` | enteros con mínimo y máximo por ruta (`size` ≤ 50, `limit` ≤ 200/100/20) | query |
| `ventana` (Cassandra) | `^\d{12}$` y fecha real (`AAAAMMDDHHMM`) | query + servicio |
| `cursor` (Cassandra) | UUID y versión 1 (timeuuid) | query + servicio |
| `desde` / `hasta` (InfluxDB) | ISO 8601 **con zona**, `desde < hasta`, `hasta − desde ≤ 3 h` | query + servicio |
| Cuerpo de comentario | `id_usuario` `U-NNNN`, alias 3–30, texto 1–500, idioma, equipo ISO, minuto 0–130 | cuerpo |
| Cuerpo de evento del acta | minuto 1–130, tipo del `VALUELIST`, descripción ≤ 200 | cuerpo (IRIS vuelve a validarlo) |
| Campos no declarados | rechazados (`extra="forbid"`) | todos los cuerpos |
| `Idempotency-Key` | obligatorio en las creaciones, formato UUID | header |
| `X-Request-ID` | opcional. Se reutiliza solo si cumple `^[A-Za-z0-9._-]{1,64}$` | header |

## 4. Formato de error (RF12, RNF4)

Todas las respuestas de error usan el mismo esquema (`ErrorRespuesta`):

```json
{
  "error": {
    "codigo": "CONFLICTO_ESTADO",
    "mensaje": "No se puede pasar de 'Programado' a 'Finalizado'. Transiciones permitidas: Programado -> En Juego -> Finalizado.",
    "request_id": "eb9629f2-4515-4440-a8cd-6e81f54ba0b3",
    "detalles": [{"estado_actual": "Programado", "estado_pedido": "Finalizado"}]
  }
}
```

| HTTP | `codigo` | Cuándo | `detalles` |
|---|---|---|---|
| 400 | `VALIDACION` | Parámetro, query, header o cuerpo inválido. JSON malformado | `[{campo, mensaje}]` |
| 404 | `RECURSO_NO_ENCONTRADO` | El recurso no existe en su fuente. Ruta inexistente | `[]` |
| 404 | `SESION_NO_VIGENTE` | La sesión no existe o expiró | `[]` |
| 405 | `METODO_NO_PERMITIDO` | Método no soportado por la ruta | `[]` |
| 409 | `CONFLICTO_ESTADO` | Transición de estado no permitida. Evento en acta Finalizada | estado actual y pedido |
| 409 | `CONFLICTO_IDEMPOTENCIA` | Misma `Idempotency-Key` con otro cuerpo, o todavía en curso | `[]` |
| 500 | `ERROR_INTERNO` | Error no previsto. El detalle técnico va solo al log | `[]` |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | La fuente rechaza la conexión, no tiene hosts o rechaza las credenciales | `[{dependencia}]` |
| 504 | `DEPENDENCIA_TIMEOUT` | La fuente no respondió dentro del timeout | `[{dependencia}]` |

**Qué nunca aparece en una respuesta:** credenciales, URIs, hosts, puertos,
consultas, nombres de clases o excepciones del driver, mensajes de `%Status`
de IRIS ni trazas. La prueba `test_error_inesperado_no_expone_detalle`
inyecta una excepción con una URI con contraseña y verifica que no llegue al
consumidor.

### Ausencia, vacío válido y dependencia caída

| Situación | Respuesta | Ejemplo |
|---|---|---|
| El recurso pedido no existe | 404 | `GET /partidos/P-999/eventos` |
| El recurso existe y la consulta no tiene resultados | 200 con lista vacía | `GET /partidos/P-002/eventos` → `eventos: []` |
| La consulta por ventana no tiene datos | 200 con lista vacía | ventana de comentarios o de estadísticas sin puntos |
| La fuente falló | 503 / 504, **nunca 200 vacío** | Redis detenido → `GET /sesiones/S-0001` = 504 |
| Respuesta degradada documentada | 200 con `X-Cache: BYPASS` | ficha del partido con Redis caído (se lee Neo4j) |

En Cassandra e InfluxDB una ventana vacía no permite distinguir "partido
inexistente" de "partido sin datos en esa ventana" sin consultar otra fuente.
Se decidió **no** consultar Neo4j en esas lecturas, porque son las más
frecuentes (muro en vivo y estadísticas en vivo), y la decisión está
documentada en el contrato. La escritura de comentarios (CU09) sí verifica el
partido en Neo4j, porque escribir sobre un partido inexistente dejaría datos
huérfanos.

## 5. Idempotencia y operaciones de escritura (RF19, RNF14)

| Endpoint | Tipo | ¿Repetible sin efectos? | Mecanismo | Qué pasa si se repite |
|---|---|---|---|---|
| Todos los GET | Lectura | Sí | No modifican datos. La lectura de sesión **no** renueva el TTL | Misma respuesta (salvo cambios de los datos) |
| `GET /partidos/{c}` | Lectura | Sí | Solo escribe la caché interna con TTL | Primera MISS, siguientes HIT |
| `DELETE /sesiones/{id}` | Invalidación | Sí, idempotente por naturaleza | `DEL` | 204 siempre: la sesión deja de ser válida |
| `PATCH /partidos-oficiales/{c}/estado` | Actualización | Sí | Pedir el estado actual no cambia nada | 200 con `cambiado: false` |
| `POST /partidos/{c}/comentarios` | Creación | Sí, con la misma clave | `Idempotency-Key` + `SET NX` en Redis (TTL 24 h) | 200 con el mismo `id_comentario` y `Idempotent-Replayed: true` |
| `POST /partidos-oficiales/{c}/eventos` | Creación | Sí, con la misma clave | Igual que comentarios | 200 con el mismo resultado. El evento no se duplica en el acta |

**Algoritmo de idempotencia** (`app/services/idempotencia.py`):

1. Se calcula la huella SHA-256 del cuerpo junto con el código de partido.
2. `SET idem:<operacion>:<clave> {huella, en_curso} NX EX 86400`.
3. Si la clave ya existía: con otra huella → 409. Con la misma huella pero
   `en_curso` → 409 (otra request todavía está escribiendo). Si ya estaba
   completada → se devuelve la respuesta guardada sin escribir.
4. Si la clave es nueva, se escribe en la fuente. Si la escritura falla
   (404, 409, 503, 504) la clave se **borra**, para que el cliente pueda
   reintentar con la misma clave.
5. Con éxito se guarda la respuesta (`SET XX KEEPTTL`).

**Duplicados y cambios parciales:**

* Sin `Idempotency-Key` la creación se rechaza (400): no hay creación sin
  protección contra reintentos.
* Dos claves distintas con el mismo texto crean **dos** comentarios. Es una
  decisión explícita: un hincha puede repetir un mensaje a propósito.
* Si Redis no está disponible no se escribe (503/504): sin el registro de la
  clave no se puede garantizar que un reintento no duplique.
* El comentario se escribe en las dos tablas con un BATCH **logged**:
  Cassandra garantiza que, si se aplica, se apliquen las dos inserciones
  (atomicidad del lote, no aislamiento).
* Si la escritura se completó pero no se pudo guardar la respuesta en Redis
  (cae justo después), la API responde éxito igual. Un reintento con esa
  clave recibe 409 "en curso" hasta que venza el TTL, nunca un duplicado.
* En IRIS, `CambiarEstado` abre el partido con bloqueo exclusivo
  (concurrencia 4). Así dos transiciones simultáneas no se pisan.

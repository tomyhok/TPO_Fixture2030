# Hito 10 — API REST Integrada del Fixture 2030

Grupo 4 — Ingeniería de Datos II

API HTTP (FastAPI) que expone los seis módulos NoSQL del TPO mediante
adaptadores separados, con validación previa, contrato OpenAPI, formato de
error único, idempotencia en las escrituras, timeouts, request ID en logs,
pruebas reproducibles y evidencia.

| Módulo | Fuente | Hito | Rutas |
|---|---|---|---|
| Equipos y jugadores | MongoDB | 4 | `GET /equipos`, `/equipos/{codigo_iso}`, `/equipos/{codigo_iso}/jugadores`, `/jugadores/{id_jugador}` |
| Partidos y relaciones | Neo4j (+ caché Redis) | 5 | `GET /partidos/{codigo_partido}`, `/partidos/{codigo_partido}/eventos`, `/equipos/{codigo_iso}/rivales` |
| Comentarios | Cassandra | 6 | `GET` y `POST /partidos/{codigo_partido}/comentarios` |
| Sesiones | Redis | 7 | `GET` y `DELETE /sesiones/{id_sesion}` |
| Estadísticas | InfluxDB 3 | 8 | `GET /partidos/{codigo_partido}/estadisticas` |
| Actas oficiales | IRIS | 9 | `GET /partidos-oficiales/{codigo_partido}`, `PATCH .../estado`, `POST .../eventos` |
| Salud | las seis | — | `GET /health` |

## Documentación

| Documento | Apartados de la sección 8 |
|---|---|
| [`docs/casos_de_uso.md`](docs/casos_de_uso.md) | Casos de uso (16 fichas con los puntos de la sección 5.1) |
| [`docs/arquitectura_y_adaptadores.md`](docs/arquitectura_y_adaptadores.md) | Arquitectura, Adaptadores, Coherencia con el TPO |
| [`docs/contratos_y_errores.md`](docs/contratos_y_errores.md) | Mapa de endpoints, Contratos, Validación, Errores, Idempotencia |
| [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md) | Conectividad (notebook vs. Docker), Seguridad, timeouts y logs |
| [`docs/pruebas_y_evidencia.md`](docs/pruebas_y_evidencia.md) | Pruebas, Rendimiento básico |
| [`docs/preguntas_guia.md`](docs/preguntas_guia.md) | Respuestas a las 20 preguntas guía |
| [`docs/evidencia/`](docs/evidencia/README.md) | Evidencia de cada endpoint contra su fuente |
| [`openapi/openapi.yaml`](openapi/openapi.yaml) | Contrato OpenAPI 3.1 (generado del código) |
| [`tests/README.md`](tests/README.md) | Cómo están organizadas y cómo se ejecutan las pruebas |

## Requisitos

* Docker Desktop con los contenedores del [`docker-compose.yml`](../docker-compose.yml) de la raíz.
* Python **3.12** en la notebook (`py -3.12` en Windows). Se eligió 3.12 por
  compatibilidad de `cassandra-driver` e `intersystems-irispython`.
* Git Bash (o cualquier bash) para los scripts `.sh`. Los scripts de uso
  diario también tienen versión `.ps1`.
* Puertos libres: 8000 (API) y los de las bases (27017, 7687, 9042, 6379, 8181, 1972).

## Puesta en marcha

Todos los comandos se ejecutan desde `fixture2030-hito-10-api-integrada/`,
salvo el primero.

```bash
# 1. Levantar las bases (desde la raíz del repositorio)
docker compose up -d

# 2. Configurar (una vez): copiar el ejemplo y completar las contraseñas.
#    MONGO_PASSWORD y NEO4J_PASSWORD son las del docker-compose.yml raíz;
#    IRIS_PASSWORD es una contraseña nueva que elige cada integrante.
cp .env.example .env

# 3. Entorno de Python (una vez)
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Linux/macOS: .venv/bin/python

# 4. Preparar los datos de las seis fuentes (idempotente)
bash scripts/preparar_datos.sh

# 5. Verificar la conectividad de cada dependencia
bash scripts/verificar_conectividad.sh

# 6. Iniciar la API (Ctrl+C para detenerla)
bash scripts/iniciar_api.sh            # PowerShell: .\scripts\iniciar_api.ps1
```

* **Swagger UI:** <http://127.0.0.1:8000/docs>
* **OpenAPI:** <http://127.0.0.1:8000/openapi.json> (igual a `openapi/openapi.yaml`)
* **Salud:** <http://127.0.0.1:8000/health>

`preparar_datos.sh` reutiliza los scripts de los hitos anteriores (Neo4j,
Cassandra, Redis, InfluxDB) y además:

* carga en InfluxDB las estadísticas de `P-001` y `P-002` con códigos
  homologados;
* compila en IRIS las clases del Hito 9 (con el nuevo `Codigo`) y la fachada
  `iris/Fixture.API.cls`;
* crea el usuario de la API con un rol mínimo;
* reinicia las actas de muestra.

No borra datos de los otros módulos.

### Ejemplos con cURL

```bash
curl http://127.0.0.1:8000/equipos/ARG
curl "http://127.0.0.1:8000/equipos?confederacion=CONMEBOL&size=5"
curl -i http://127.0.0.1:8000/partidos/P-001                       # ver X-Cache
curl "http://127.0.0.1:8000/partidos/P-001/comentarios?ventana=203006152015&limit=3"
curl -i -X POST http://127.0.0.1:8000/partidos/P-001/comentarios \
  -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"id_usuario":"U-1001","usuario_alias":"hincha","equipo_apoyado":"ARG","texto":"Vamos","idioma":"es","minuto_partido":10}'
curl http://127.0.0.1:8000/sesiones/S-0001
curl "http://127.0.0.1:8000/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:30:00Z&resolucion=5m"
curl -X PATCH http://127.0.0.1:8000/partidos-oficiales/P-002/estado -H "Content-Type: application/json" -d '{"estado":"En Juego"}'
```

Todos los escenarios, incluidos los de error, están en la colección Postman
y en `scripts/generar_evidencia.sh`, cuya salida queda en `docs/evidencia/`.

## Pruebas

```bash
bash scripts/ejecutar_pruebas.sh unit   # 122 unitarias, sin Docker
bash scripts/ejecutar_pruebas.sh        # + conectividad + 35 de integración contra las bases
```

**Método:** pytest para las pruebas automáticas (unitarias con dobles de los
adaptadores, e integración con la API real contra las bases reales), cURL para
la evidencia reproducible y Swagger UI para la exploración manual. Ver
[`docs/pruebas_y_evidencia.md`](docs/pruebas_y_evidencia.md).

Para regenerar la evidencia y la medición de latencia, con la API levantada:

```bash
bash scripts/generar_evidencia.sh --con-caida   # --con-caida detiene Redis unos segundos y lo vuelve a iniciar
```

Si se cambia una ruta o un schema, se regenera el contrato con
`.venv/Scripts/python scripts/exportar_openapi.py`. La prueba de contrato
falla si queda desactualizado.

## Colección Postman

[`postman/fixture2030_collection.json`](postman/fixture2030_collection.json)
tiene 64 requests con pruebas automáticas (264 aserciones), que cubren los 16
casos de uso y sus escenarios de error. Se importa junto con el environment
`postman/fixture2030_local.postman_environment.json`. Antes de cada corrida
completa hay que ejecutar `bash scripts/reiniciar_muestra.sh`. Instrucciones
en [`postman/README.md`](postman/README.md).

Desde la terminal, con Node.js: `bash scripts/ejecutar_postman.sh`.

## Modo contenedor (opcional)

La API también puede correr dentro de la red de Docker, donde las bases se
alcanzan por el nombre del servicio. Desde la raíz del repositorio:

```bash
docker compose -f docker-compose.yml -f fixture2030-hito-10-api-integrada/docker-compose.api.yml up -d --build api
curl http://127.0.0.1:8001/health
```

Las diferencias de hosts y puertos entre la notebook y el contenedor están en
[`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md).

## Detener sin borrar datos

* API: `Ctrl+C` (o `docker compose ... rm -sf api` en modo contenedor).
* Bases: `docker compose stop` o `docker compose down` desde la raíz,
  **nunca** `down -v`.

## Estructura

```text
fixture2030-hito-10-api-integrada/
├── README.md
├── requirements.txt · pytest.ini · .env.example · .gitignore
├── Dockerfile · docker-compose.api.yml          modo contenedor (opcional)
├── app/
│   ├── main.py                    creación de la app, tags y metadatos del contrato
│   ├── dependencias.py            composición: adaptadores -> servicios -> rutas
│   ├── routes/                    contrato HTTP por módulo
│   ├── services/                  casos de uso + idempotencia
│   ├── adapters/                  mongo, neo4j, cassandra, redis, influx, iris (+ base común)
│   ├── schemas/                   modelos Pydantic de request/response
│   ├── core/                      errores, request ID, logs, middleware, OpenAPI
│   └── config/                    settings desde variables de entorno
├── iris/Fixture.API.cls           fachada de objetos que invoca el adaptador IRIS
├── openapi/openapi.yaml
├── postman/                       colección (64 requests) + environments local y contenedor
├── scripts/
│   ├── iniciar_api.sh|ps1 · verificar_conectividad.sh|ps1|py · ejecutar_pruebas.sh|ps1
│   ├── preparar_datos.sh · reiniciar_muestra.sh|ps1 · ejecutar_postman.sh
│   ├── generar_evidencia.sh · medir_latencia.py · exportar_openapi.py
│   └── datos/cargar_estadisticas_influx.py
├── tests/
│   ├── unit/                      122 pruebas sin bases (dobles en memoria)
│   ├── integration/               35 pruebas contra las seis bases
│   └── README.md
└── docs/
    ├── casos_de_uso.md · arquitectura_y_adaptadores.md · contratos_y_errores.md
    ├── conectividad_y_configuracion.md · pruebas_y_evidencia.md · preguntas_guia.md
    └── evidencia/
```

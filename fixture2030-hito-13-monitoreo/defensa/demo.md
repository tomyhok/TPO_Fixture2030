# Estrategia de Demostración en Vivo y Plan de Contingencia (RNF7)

Este documento detalla la secuencia exacta de comandos y pantallas para la demostración durante la defensa ante la FIFA (**Sección 6.3**), junto con el **Plan B de contingencia (RNF7)** en caso de que algún contenedor o puerto local falle durante la exposición.

---

## 1. Preparación Previa (5 minutos antes de exponer)

Ejecutar en dos terminales antes de comenzar los 20 minutos para no perder tiempo de exposición esperando el arranque de contenedores:

### Terminal 1 — Bases de datos y Stack de Monitoreo
```bash
# 1. Levantar los 6 motores NoSQL desde la raíz del repositorio
cd c:/Projects/TPO_Fixture2030
docker compose up -d

# 2. Levantar Prometheus, Grafana y Node Exporter (Hito 13)
cd fixture2030-hito-13-monitoreo
bash scripts/iniciar_monitoreo.sh
```

### Terminal 2 — API REST Integrada (Hito 10/11/13)
```bash
cd c:/Projects/TPO_Fixture2030/fixture2030-hito-10-api-integrada
# Escuchar en 0.0.0.0:8000 para que Prometheus (host.docker.internal:8000) recolecte /metrics
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Pestañas del Navegador listas en orden:
1. **Presentación:** [`defensa/presentacion.html`](presentacion.html)
2. **Swagger UI (Contrato OpenAPI):** `http://localhost:8000/docs`
3. **Métricas crudas de la API:** `http://localhost:8000/metrics`
4. **Targets y Alertas de Prometheus:** `http://localhost:9090/targets` y `http://localhost:9090/alerts`
5. **Dashboard Grafana War Room:** `http://localhost:3000/d/fixture2030-war-room` (`admin` / `fixture2030`)

---

## 2. Secuencia Corta y Reproducible de Demostración (5 Minutos en Vivo)

### Paso A — Las 6 lecturas de negocio vinculadas a cada decisión de base de datos (2 min)

Ejecutar desde terminal (o desde la colección Postman [`fixture2030_collection.json`](../../fixture2030-hito-10-api-integrada/postman/fixture2030_collection.json)):

```bash
# 1. Documental (MongoDB): Ficha completa por clave indexada IXSCAN
curl -i http://localhost:8000/equipos/ARG

# 2. Grafo (Neo4j): Recorrido Partido <- Evento <- Jugador
curl -i "http://localhost:8000/partidos/P-001/eventos?limit=5"

# 3. Columnar (Cassandra): Muro particionado por (partido, ventana, shard) y ordenado por TIMEUUID
curl -i "http://localhost:8000/partidos/P-001/comentarios?ventana=203006152016&limit=5"

# 4. Clave-Valor (Redis): Sesión en memoria con HGETALL + TTL en pipeline (noeviction)
curl -i http://localhost:8000/sesiones/S-0001

# 5. Series Temporales (InfluxDB 3): Estadísticas agregadas con DATE_BIN
curl -i "http://localhost:8000/partidos/P-001/estadisticas?desde=2030-06-10T20:00:00Z&hasta=2030-06-10T20:15:00Z&resolucion=1m"

# 6. Orientado a Objetos (IRIS): Acta oficial P-009 con árbitro y eventos validados por regla AgregarEvento
curl -i http://localhost:8000/partidos-oficiales/P-009
```

**Qué señalar al ejecutar:**
- Todas las respuestas incluyen el header `X-Request-ID`.
- Cada llamada incrementa en vivo `fixture_db_operations_total{db="<motor>"}` y registra su latencia en `fixture_db_operation_duration_seconds_bucket`.

---

### Paso B — Observabilidad en Grafana y Prueba de Falla Controlada (3 min)

1. Mostrar en **Grafana (`http://localhost:3000/d/fixture2030-war-room`)** que los 3 targets (`up`) y las 6 bases (`fixture_db_up`) están en **verde (`1`)**, y cómo el panel **"Comparación de Latencia por Base de Datos NoSQL"** distingue los tiempos de respuesta de cada motor.
2. Ejecutar la falla controlada reversible sobre Redis:
   ```bash
   docker stop fixture2030-redis
   curl -i http://localhost:8000/sesiones/S-0001          # -> 503 DEPENDENCIA_NO_DISPONIBLE
   curl -i http://localhost:8000/equipos/ARG              # -> 200 OK (Aislamiento demostrado)
   curl -s "http://localhost:8000/health/dependencias?refrescar=true"
   ```
3. Mostrar en Grafana (tras `15s` de refresh) cómo:
   - `fixture_db_up{db="redis"}` pasa a **rojo (`0 - NO DISPONIBLE`)** mientras las otras 5 bases siguen en **verde (`1`)**.
   - El panel de errores suma `DEPENDENCIA_NO_DISPONIBLE (/sesiones/{id_sesion})`.
4. Recuperar el servicio sin perder datos:
   ```bash
   docker start fixture2030-redis
   curl -s "http://localhost:8000/health/dependencias?refrescar=true"
   ```

---

## 3. Plan B de Contingencia ante Fallas de Entorno Local (RNF7)

Para cumplir con **RNF7 (Disponibilidad durante la defensa)**, si durante la exposición ocurre algún inconveniente con Docker Desktop, un puerto local ocupado o la red de la notebook, el equipo cuenta con tres niveles de respaldo inmediatos dentro del propio repositorio:

1. **Nivel 1 — Evidencia estructurada del Hito 13 lista para abrir:**
   - [`evidencia/prometheus_targets.txt`](../evidencia/prometheus_targets.txt) y [`evidencia/prometheus_targets.json`](../evidencia/prometheus_targets.json): estado de los 3 targets, las 4 reglas de alerta y las series `fixture_db_up` y `/metrics`.
   - [`evidencia/prueba_de_falla.md`](../evidencia/prueba_de_falla.md) y [`evidencia/prueba_de_falla.json`](../evidencia/prueba_de_falla.json): tabla comparativa completa de las 3 fases (antes, durante `docker stop` y después de `docker start`).
   - [`evidencia/dashboards/`](../evidencia/dashboards/): vistas y capturas de los paneles de Grafana y Prometheus.
2. **Nivel 2 — Ejecución instantánea sin Docker (en memoria con dobles y TestClient):**
   - Si Docker Desktop no responde, se puede demostrar en vivo la instrumentación de `/metrics`, el aislamiento de fallas `503`/`504` y las pruebas de salud corriendo en `2 segundos`:
     ```bash
     pytest ../fixture2030-hito-10-api-integrada/tests/unit -v
     ```
3. **Nivel 3 — Evidencia histórica trazable de los Hitos 4 a 12:**
   - Hito 11 (Matriz de 9 capas sobre los 6 motores): [`../fixture2030-hito-11-conectividad/docs/matriz_de_conectividad.md`](../../fixture2030-hito-11-conectividad/docs/matriz_de_conectividad.md).
   - Hito 12 (Benchmark antes/después Cassandra vs Redis): [`../fixture2030-hito-12-carga-optimizacion/docs/evidencia/comparacion.md`](../../fixture2030-hito-12-carga-optimizacion/docs/evidencia/comparacion.md).

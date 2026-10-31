# Hito 13 — Monitoreo con Prometheus + Grafana y Defensa Final del Fixture 2030

**Grupo 4 — Ingeniería de Datos II (UADE)**

Capa de observabilidad transversal de la plataforma **Fixture Mundial 2030** con **Prometheus**, **Grafana** y **Node Exporter**, integrada con el endpoint `GET /metrics` de la **API REST del Hito 10** para monitorear la disponibilidad, latencia, throughput y errores de aplicación y de los **6 motores NoSQL** (**MongoDB, Neo4j, Cassandra, Redis, InfluxDB 3 e InterSystems IRIS**), junto con el material completo para la defensa técnica de 20 minutos ante la FIFA.

---

## 1. Documentación y Materiales de Defensa

| Archivo | Contenido | Requisitos cubiertos |
|---|---|---|
| [`docs/inventario_de_componentes.md`](docs/inventario_de_componentes.md) | Inventario de los 9 componentes, modelo de datos, función, puerto, mecanismo de monitoreo, métricas, riesgos y limitaciones. | RF2, RF3, RNF3, §5.1 |
| [`docs/metricas_y_consultas.md`](docs/metricas_y_consultas.md) | Configuración de Prometheus, diferenciación aplicación vs. infraestructura, procedimientos `UP`/`DOWN` y 6 consultas PromQL explicadas. | RF1, RF4, RF8, RNF4, §5.2 |
| [`docs/alertas_y_umbral.md`](docs/alertas_y_umbral.md) | Marco SLI/SLO/SLA (`< 100ms`, `99.99%`) y especificación operativa de las 4 reglas de alerta en [`prometheus/reglas-o-alertas.yml`](prometheus/reglas-o-alertas.yml). | RF9, §5.4 |
| [`docs/decisiones_de_arquitectura.md`](docs/decisiones_de_arquitectura.md) | Defensa de los 6 modelos NoSQL (los 10 puntos de §6.4 por base), relación con los objetivos del TPO y análisis de 4 mejoras transversales. | RF11, RF12, RF14, RF15, §6.4 |
| [`docs/limitaciones_y_evidencia.md`](docs/limitaciones_y_evidencia.md) | Separación honesta entre mediciones reales de laboratorio, objetivos de diseño y proyecciones, más matriz de trazabilidad y seguridad. | RNF2, RNF3, RNF6, RNF8 |
| [`docs/defensa_final.md`](docs/defensa_final.md) | Respuesta a la pregunta central del TPO (§11) y banco de respuestas técnicas a las 14 preguntas de la FIFA (§6.5) vinculadas con evidencia real. | RF13, RF16, §6.5, §11 |
| [`defensa/presentacion.html`](defensa/presentacion.html) | Presentación interactiva en HTML (10 diapositivas) lista para proyectar durante la defensa ante la FIFA. | RF13, §6.3.a |
| [`defensa/guion_de_20_minutos.md`](defensa/guion_de_20_minutos.md) | Distribución minuto a minuto y por integrante para cumplir estrictamente los 20 minutos máximos. | RF13, RNF12, §6.2 |
| [`defensa/demo.md`](defensa/demo.md) | Secuencia paso a paso de demostración en vivo (Swagger, Postman, Grafana, falla controlada) y Plan B de contingencia. | RNF7, §6.3 |
| [`grafana/README.md`](grafana/README.md) | Detalle del provisioning automático y de los 8 paneles del dashboard [`fixture2030_war_room.json`](grafana/dashboards/fixture2030_war_room.json). | RF5, RF6, RF7, §5.3 |
| [`evidencia/`](evidencia/) | Salidas de targets (`prometheus_targets.*`), prueba controlada de 3 fases (`prueba_de_falla.*`), vista del dashboard y escaneo de secretos. | RF10, RNF2, RNF6, RNF11 |

---

## 2. Requisitos Previos

- Docker Desktop con Docker Compose.
- Los contenedores de los 6 motores NoSQL levantados desde el [`../docker-compose.yml`](../docker-compose.yml) raíz y datos de muestra preparados (`bash ../fixture2030-hito-10-api-integrada/scripts/preparar_datos.sh`).
- La API REST integrada del Hito 10 iniciada en el puerto `8000` (escuchando en `0.0.0.0:8000` para que el contenedor de Prometheus pueda alcanzar `host.docker.internal:8000/metrics`).
- Puertos locales disponibles para monitoreo: `9090` (Prometheus), `3000` (Grafana) y `9100` (Node Exporter).

---

## 3. Inicio Rápido y Reproducibilidad (RNF1)

### Paso 1: Levantar las bases y la API integrada (con `/metrics`)

```bash
# Desde la raíz del repositorio:
docker compose up -d

# En otra terminal, iniciar la API integrada exponiendo /metrics en 0.0.0.0:8000
cd fixture2030-hito-10-api-integrada
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verificar que la API expone métricas en formato Prometheus:
```bash
curl -s http://localhost:8000/metrics | head -n 25
```

### Paso 2: Iniciar Prometheus, Grafana y Node Exporter

Desde `fixture2030-hito-13-monitoreo/`:

```bash
bash scripts/iniciar_monitoreo.sh
# O desde PowerShell:
# .\scripts\iniciar_monitoreo.ps1
```

Servicios disponibles:

| Servicio | Contenedor | URL de Acceso | Credenciales de Laboratorio |
|---|---|---|---|
| **Prometheus** | `fixture2030-prometheus` | `http://localhost:9090` (`/targets`, `/alerts`, `/graph`) | Sin autenticación (local) |
| **Grafana** | `fixture2030-grafana` | `http://localhost:3000/d/fixture2030-war-room` | `admin` / `fixture2030` |
| **Node Exporter** | `fixture2030-node-exporter` | `http://localhost:9100/metrics` | Sin autenticación (local) |
| **API `/metrics`** | Host (`:8000`) | `http://localhost:8000/metrics` | Sin autenticación (local) |

### Paso 3: Verificar Targets y Reglas en Prometheus

```bash
bash scripts/verificar_targets.sh
# O desde PowerShell: .\scripts\verificar_targets.ps1
```
Consulta `/api/v1/targets`, `/api/v1/rules`, `up` y `fixture_db_up`, y actualiza [`evidencia/prometheus_targets.json`](evidencia/prometheus_targets.json) y [`evidencia/prometheus_targets.txt`](evidencia/prometheus_targets.txt).

### Paso 4: Ejecutar Prueba Controlada y Reversible de Falla (RF10, RNF11)

```bash
bash scripts/ejecutar_prueba_controlada.sh
# O desde PowerShell: .\scripts\ejecutar_prueba_controlada.ps1
```
Ejecuta las 3 fases (1: tráfico normal en las 6 bases; 2: `docker stop fixture2030-redis`, comprobando `503` en `/sesiones/S-0001`, `200 OK` en `/equipos/ARG` y caída de `fixture_db_up{db="redis"}` a `0`; 3: `docker start fixture2030-redis` y recuperación a `1`) sin borrar volúmenes ni alterar datos funcionales. Guarda los resultados en [`evidencia/prueba_de_falla.json`](evidencia/prueba_de_falla.json) y [`evidencia/prueba_de_falla.md`](evidencia/prueba_de_falla.md).

### Paso 5: Validación sin Docker y Escaneo de Secretos (RNF6)

```bash
python scripts/generar_evidencia_y_validar.py
```

### Paso 6: Limpieza Segura del Entorno (RNF11)

```bash
bash scripts/limpiar_entorno.sh
# O desde PowerShell: .\scripts\limpiar_entorno.ps1
```
Detiene únicamente los contenedores de monitoreo (`prometheus`, `grafana`, `node-exporter`) sin eliminar ningún volumen de datos de las bases NoSQL.

---

## 4. Estructura del Módulo (Sección 8 de la Consigna)

```text
fixture2030-hito-13-monitoreo/
├── README.md
├── docker-compose.yml
├── prometheus.yml
├── .gitignore
├── prometheus/
│   └── reglas-o-alertas.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml
│   │   └── dashboards/
│   │       └── dashboards.yml
│   ├── dashboards/
│   │   └── fixture2030_war_room.json
│   └── README.md
├── scripts/
│   ├── iniciar_monitoreo.sh / .ps1
│   ├── verificar_targets.py / .sh / .ps1
│   ├── ejecutar_prueba_controlada.py / .sh / .ps1
│   ├── generar_evidencia_y_validar.py
│   └── limpiar_entorno.sh / .ps1
├── docs/
│   ├── inventario_de_componentes.md
│   ├── metricas_y_consultas.md
│   ├── alertas_y_umbral.md
│   ├── decisiones_de_arquitectura.md
│   ├── limitaciones_y_evidencia.md
│   └── defensa_final.md
├── evidencia/
│   ├── prometheus_targets.json / .txt
│   ├── dashboards/
│   │   ├── README.md
│   │   └── vista_dashboard_war_room.svg
│   ├── prueba_de_falla.json / .md
│   └── resultados_sin_secretos/
│       ├── muestra_endpoint_metrics.prom
│       ├── muestra_metrics_durante_falla.prom
│       └── verificacion_secretos.txt
└── defensa/
    ├── presentacion.html
    ├── guion_de_20_minutos.md
    └── demo.md
```

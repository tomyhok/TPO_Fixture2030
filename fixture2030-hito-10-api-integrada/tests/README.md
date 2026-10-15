# Pruebas de la API — Hito 10

| Carpeta | Necesita bases | Qué prueba |
|---|---|---|
| `unit/` | No | Rutas, validación, servicios, errores, idempotencia y contrato OpenAPI, con dobles en memoria de los seis adaptadores (`unit/dobles.py`). También la traducción de las excepciones reales de cada driver. |
| `integration/` | Sí (las seis) | La API real contra las fuentes reales: un caso por módulo, ausencia, vacío válido, sesión expirada, paginación, escritura repetida, dependencias caídas y lentas. |

## Ejecutar

Desde `fixture2030-hito-10-api-integrada/`:

```bash
bash scripts/ejecutar_pruebas.sh unit   # solo unitarias (no necesita Docker)
bash scripts/ejecutar_pruebas.sh        # unitarias + conectividad + integración
```

En PowerShell: `.\scripts\ejecutar_pruebas.ps1 [unit]`.

También directamente con pytest:

```bash
.venv/Scripts/python -m pytest tests/unit -q
.venv/Scripts/python -m pytest -m integracion -v
```

## Requisitos de la integración

1. Contenedores levantados (`docker compose up -d` en la raíz).
2. `.env` completo (copiado de `.env.example`).
3. `bash scripts/preparar_datos.sh` ejecutado al menos una vez.

Si alguna fuente no responde, las pruebas de integración se saltean e indican
cuál falta. Las pruebas de IRIS reinician las actas P-001..P-003 con
`Fixture.API.CargarMuestra()`, así que se pueden repetir. Las de comentarios
crean comentarios nuevos en la ventana del minuto actual. Las de sesiones usan
claves `S-8xxx` con TTL corto.

Las pruebas de dependencias caídas **no** detienen contenedores: apuntan la
API a un puerto libre o a un servidor TCP que nunca responde. La caída real
con `docker stop` está en `scripts/generar_evidencia.sh --con-caida`.

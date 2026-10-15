# Colección Postman — Hito 10

| Archivo | Contenido |
|---|---|
| `fixture2030_collection.json` | 64 requests en 8 carpetas (una por módulo, más salud y errores generales), con pruebas en cada una |
| `fixture2030_local.postman_environment.json` | `baseUrl = http://127.0.0.1:8000` (API en la notebook) |
| `fixture2030_contenedor.postman_environment.json` | `baseUrl = http://127.0.0.1:8001` (API en contenedor, `docker-compose.api.yml`) |

## Importar en Postman

1. **Import** → arrastrar los tres archivos `.json` de esta carpeta.
2. Arriba a la derecha, elegir el environment **Fixture 2030 - API local**.
3. Antes de cada corrida completa, ejecutar `bash scripts/reiniciar_muestra.sh`
   (o `.ps1`). Recarga las sesiones de Redis, que vencen a los 30 minutos, y
   deja las actas de IRIS en su estado inicial.
4. Clic derecho sobre la colección → **Run collection** → **Run**. Las
   requests dependen del orden, por ejemplo la página 2 del muro usa el cursor
   de la página 1 y el reintento usa la misma `Idempotency-Key`.

Cada request se puede abrir y enviar suelta para explorar. En la pestaña
**Tests** está qué se verifica.

## Qué prueba

| Carpeta | Escenarios |
|---|---|
| 00 Salud | `/health` con las seis fuentes ok |
| 01 MongoDB | ficha, 404, 400, paginación con filtro y orden, página vacía, plantel por posición, jugador |
| 02 Neo4j | ficha con `X-Cache` MISS → HIT, 404, eventos con protagonista, partido sin eventos (200 `[]`) vs. inexistente (404), rivales con `limit` |
| 03 Cassandra | muro paginado con cursor sin solapamiento, ventana vacía, ventana inválida, alta 201, reintento 200 con el mismo id, verificación de que no se duplicó, 409 con otro cuerpo, 404, falta de `Idempotency-Key`, campos extra |
| 04 Redis | sesión vigente sin datos internos, inexistente, inválida, cierre idempotente, sesión cerrada |
| 05 InfluxDB | partido completo a 5m (la posesión suma 100), un equipo a 1m, tope de puntos, ventana vacía, intervalos inválidos |
| 06 IRIS | ciclo de vida del acta P-002: transición inválida 409, válida 200, repetida sin cambios, evento 201, reintento sin duplicar, 400, Finalizado, evento tardío 409 |
| 07 Errores generales | ruta inexistente, 405, JSON malformado, reutilización de `X-Request-ID` |

Además, un script a nivel colección verifica en **todas** las respuestas el
header `X-Request-ID` y, en los errores, el formato común con el mismo
`request_id`.

Los escenarios de **dependencia caída** no están en la colección, porque
requieren detener un contenedor. Ver `scripts/generar_evidencia.sh --con-caida`
y `tests/integration/test_dependencias_caidas.py`.

## Desde la terminal (Newman)

```bash
bash scripts/ejecutar_postman.sh              # API de la notebook
bash scripts/ejecutar_postman.sh contenedor   # API en contenedor
```

Requiere Node.js. La salida de una corrida está en
[`../docs/evidencia/15_postman_newman.txt`](../docs/evidencia/15_postman_newman.txt).

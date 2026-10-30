# Hito 12: Pruebas de carga y optimización

**Flujo probado:** muro de comentarios en vivo de un partido durante un pico post-gol. Se compara la lectura directa de Cassandra (Hito 6) con la lectura de un muro precomputado en Redis (Hito 7).

## Documentación

| Documento | Contenido |
|---|---|
| [docs/flujo_y_escenario_de_carga.md](docs/flujo_y_escenario_de_carga.md) | Flujo, operaciones, escenario de carga |
| [datos-o-generadores/README.md](datos-o-generadores/README.md) | Datos de prueba, distribución, volumen |
| [docs/linea_base.md](docs/linea_base.md) | Línea base medida |
| [docs/hipotesis_y_optimizacion.md](docs/hipotesis_y_optimizacion.md) | Cuello de botella, optimización, repetición, comparación, trade-offs |
| [docs/integridad_y_limitaciones.md](docs/integridad_y_limitaciones.md) | Validación de integridad y límites del experimento |
| [docs/integracion_data_mart.md](docs/integracion_data_mart.md) | Propuesta de Data Mart |
| [docs/comparacion_relacional.md](docs/comparacion_relacional.md) | Alternativa relacional |
| [compose-o-instrucciones-del-entorno.md](compose-o-instrucciones-del-entorno.md) | Servicios, versiones, hardware |
| [docs/evidencia/](docs/evidencia/) | Resultados crudos (JSON/CSV), integridad, comparación, log |

## Requisitos

- Docker con los servicios `cassandra` y `redis` del `docker-compose.yml` raíz.
- Python 3.10 o superior.

## Ejecución

Todos los comandos se corren desde esta carpeta.

```bash
# 0. Entorno
docker compose -f ../docker-compose.yml up -d cassandra redis   # o: docker start fixture2030-cassandra fixture2030-redis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Preparación: keyspace fixture2030_carga + 100.000 comentarios históricos (idempotente)
python scripts/preparar_datos.py --filas 100000 --semilla 2030

# 2. Línea base (muro desde Cassandra) + validación de integridad
bash scripts/ejecutar_linea_base.sh                 # capacidad: sin pausa
bash scripts/ejecutar_linea_base.sh --tasa 10       # carga fija: 500 ops/s

# 3. Prueba optimizada (muro en Redis) con los mismos parámetros
bash scripts/ejecutar_prueba_optimizada.sh
bash scripts/ejecutar_prueba_optimizada.sh --tasa 10

# 4. Comparar (tabla en docs/evidencia/comparacion.md)
python scripts/comparar_resultados.py docs/evidencia/resultados/base_X.json docs/evidencia/resultados/optimizado_Y.json
```

`scripts/ejecutar_todo.sh` corre los pasos 2 y 3 en orden (~25 min).

| Script | Etapa |
|---|---|
| `preparar_datos.py` | Preparación y generación de la carga inicial |
| `ejecutar_carga.py` | Carga y medición (lo usan los dos wrappers `.sh`) |
| `validar_integridad.py` | Validación |
| `comparar_resultados.py` | Comparación antes/después |
| `limpiar_datos_de_prueba.py` | Limpieza opcional |
| `comun.py` | Conexiones y lectura del muro (base y optimizada) |

Parámetros de `ejecutar_carga.py`: `--usuarios 50 --procesos 3 --rampa 30 --duracion 120 --lecturas 0.8 --tasa 0 --semilla 2030`.

## Limpieza segura

```bash
python scripts/limpiar_datos_de_prueba.py --confirmar
```

Solo borra el keyspace `fixture2030_carga` y las claves `muro:*` de Redis. No toca el keyspace `fixture2030` del Hito 6, las claves del Hito 7, los volúmenes de Docker ni la evidencia. No hace falta limpiar entre corridas: cada una escribe en las ventanas del minuto en que se ejecuta.

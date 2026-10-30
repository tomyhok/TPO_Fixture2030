# Datos de prueba

Todos los datos son **sintéticos**: los generan los scripts del equipo. No hay datos personales: los usuarios son `U-000123` y los alias `hincha_000123`.

## 1. Carga inicial (`scripts/preparar_datos.py`)

| Aspecto | Valor |
|---|---|
| Origen | Generados. Siguen la misma distribución que `fixture2030-cassandra/tools/generar_comentarios.py` (Hito 6), simplificada |
| Cantidad | 100 000 comentarios, cada uno en las 2 tablas (200 000 filas) |
| Partidos | 64 (`P-001`..`P-064`). **Clave caliente:** P-001 recibe el 50 % (50 477 comentarios) |
| Usuarios | 200 000 posibles. El 30 % de los comentarios sale de los 5 000 más activos |
| Timestamps | Calendario 2030: cada partido en su día y horario, minuto 0-119 al azar |
| Reproducibilidad | Semilla fija (`--semilla 2030`). Los `timeuuid` salen del instante y del número de fila, así que la misma semilla produce los mismos ids y volver a correr el script no duplica nada (en Cassandra el INSERT es un upsert) |
| Validación | Al terminar se cuenta con `COUNT(*)` en las dos tablas y se compara con las filas generadas. Resultado en `docs/evidencia/resultados/preparacion.json` |

Esta carga histórica cae en ventanas de 2030. El muro en vivo lee las ventanas del minuto **actual**, así que no lee estas filas. Su función es que las tablas y el disco de Cassandra tengan volumen, como en un torneo ya avanzado, y no estén vacíos.

## 2. Datos generados durante la carga (`scripts/ejecutar_carga.py`)

- Cada escritura crea un comentario nuevo con `timeuuid` del instante real, en la ventana del minuto en curso.
- Cada comentario intentado se guarda en `<corrida>_escrituras.csv`, con su id, partición y estado (`ok` o `error`). Ese archivo es la base de la validación de integridad.
- Las elecciones de partido, usuario y tipo de operación salen de `random.Random(semilla + nro_usuario)`. La secuencia de decisiones es la misma en cada corrida, pero la cantidad total depende de cuán rápido responda el sistema.

## 3. Volumen probado y volumen proyectado

| | Laboratorio | Proyección Fixture 2030 (estimada, no medida) |
|---|---|---|
| Comentarios en la base | ~100 000 iniciales + lo que escribe cada corrida | Decenas de millones en el torneo |
| Escrituras por segundo | Las que se midan (ver comparación) | Miles por segundo en un pico de un partido masivo |
| Nodos Cassandra | 1, en una notebook | Cluster de varios nodos con replicación 3 |

Cassandra particiona por `(partido, ventana, shard)`, así que el costo de leer el muro no depende del total de filas de la base sino de cuántas particiones se tocan. Por eso el volumen histórico más chico no invalida la medición de la lectura. Sí la limita en compactación y uso de disco.

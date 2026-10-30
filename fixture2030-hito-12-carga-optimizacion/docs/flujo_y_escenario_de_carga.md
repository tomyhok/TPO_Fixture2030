# Flujo y escenario de carga

## 1. Flujo seleccionado: muro de comentarios en vivo

**Situación del Fixture:** minuto 70 de un partido popular (P-001), justo después de un gol. Miles de hinchas publican comentarios y, sobre todo, refrescan el muro del partido para leer lo último.

| Aspecto | Definición |
|---|---|
| Consumidor | Hincha usando la app durante el partido (simulado por un usuario virtual) |
| Operaciones | **Lectura** del muro (últimos 20 comentarios de un partido) y **escritura** (publicar un comentario) |
| Fuentes | Cassandra (Hito 6): `comentarios_por_partido` y `comentarios_por_usuario`. Redis (Hito 7): solo en la versión optimizada |
| Datos que recibe | Lectura: `id_partido`. Escritura: `id_partido`, `id_usuario`, texto |
| Respuesta esperada | Lectura: lista de hasta 20 comentarios ordenados del más nuevo al más viejo. Escritura: confirmación de las dos tablas |
| Criterio de éxito | La operación termina sin excepción en menos de 2 s (timeout del driver). En una escritura, **las dos** inserciones tienen que quedar confirmadas |
| Errores registrados | Timeouts, errores del driver y fallas de Redis, por tipo de excepción. Una escritura con error queda marcada como `rechazada` en el CSV y después se controla que no haya quedado escrita a medias |

Cliente: generador en Python (`scripts/ejecutar_carga.py`) que usa los drivers directamente (`cassandra-driver` y `redis-py`). No hay API HTTP intermedia: así se mide la base y no un framework web.

### Cómo se lee el muro

- **Línea base:** el modelo del Hito 6 parte cada partido en particiones de 1 minuto × 4 shards. Para mostrar "lo último", el muro consulta las últimas 3 ventanas × 4 shards, es decir **12 consultas** a Cassandra en paralelo (`execute_async`). Después une los resultados, los ordena por `timeuuid` y se queda con 20.
- **Optimizado:** el muro de cada partido se mantiene precomputado en una lista de Redis (`muro:<partido>`, últimos 100). La lectura es **un `LRANGE`**. Detalle en [hipotesis_y_optimizacion.md](hipotesis_y_optimizacion.md).

## 2. Escenario de carga

| Parámetro | Valor | Dónde se configura |
|---|---|---|
| Datos iniciales | 100 000 comentarios históricos de los 64 partidos (ver [datos](../datos-o-generadores/README.md)) | `preparar_datos.py --filas` |
| Usuarios virtuales | 50 hilos repartidos en 3 procesos | `--usuarios`, `--procesos` |
| Mezcla de operaciones | 80 % lecturas / 20 % escrituras | `--lecturas 0.8` |
| Distribución de claves | 50 % del tráfico va a P-001 (clave caliente) y el resto se reparte uniforme entre los 64 partidos. Usuarios: 30 % del tráfico concentrado en 5 000 usuarios activos, sobre un total de 200 000 | `comun.elegir_partido / elegir_usuario` |
| Calentamiento y rampa | 30 s: los usuarios arrancan escalonados, uno cada 0,6 s. Las operaciones de la rampa **no se cuentan** en las métricas | `--rampa 30` |
| Sostenimiento | 120 s con los 50 usuarios activos. Es el período que se mide | `--duracion 120` |
| Tasa objetivo | Dos variantes (ver abajo) | `--tasa` |
| Condición de finalización | Termina al cumplirse rampa + sostenimiento. Interrupción segura con Ctrl+C: los procesos terminan su operación en curso y los resultados se guardan igual | |
| Timeout y error | Timeout de 2 s por consulta. El error se registra y el usuario sigue con la operación siguiente, sin reintentos (un reintento escondería el error en la latencia) | `comun.conectar_cassandra` |
| Limpieza y reutilización | Las corridas escriben en las ventanas del minuto real, así que no se pisan entre sí. Los wrappers esperan 60 s antes de cada corrida. Al arrancar, el modo optimizado borra `muro:*` para empezar con Redis frío. Limpieza total: `limpiar_datos_de_prueba.py --confirmar` | |

### Dos variantes del mismo escenario

1. **Capacidad (`--tasa 0`):** cada usuario manda la operación siguiente apenas termina la anterior (lazo cerrado). Mide cuántas operaciones por segundo soporta el sistema. Como la cantidad de operaciones depende de la velocidad de respuesta, el modo optimizado también **escribe más**.
2. **Carga fija (`--tasa 10`):** cada usuario hace 10 ops/s, lo que suma **500 ops/s ofrecidas**, alrededor del 70 % de la capacidad medida en la línea base. Los dos modos reciben la misma carga, así que acá se comparan latencias en igualdad de condiciones.

## 3. Proyección y límites

Un partido muy popular del Mundial podría tener cientos de miles de usuarios conectados. Con 50 usuarios virtuales sin pausa se generan cientos o miles de operaciones por segundo, y eso representa a muchos más usuarios reales, que leen cada varios segundos. **No** se ejecuta el volumen real del torneo: ver [integridad_y_limitaciones.md](integridad_y_limitaciones.md).

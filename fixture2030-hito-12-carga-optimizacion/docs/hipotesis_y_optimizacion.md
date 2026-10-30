# Hipótesis, optimización y comparación

## 1. Hipótesis del cuello de botella

**Observación:** en la línea base cada lectura del muro hace 12 consultas a Cassandra (3 ventanas × 4 shards). Las lecturas son el 80 % de las operaciones, así que con 500 ops/s eso suma unas **4 800 consultas/s** solo para el muro, todas sobre las mismas particiones calientes de P-001.

**Hipótesis H1:** la latencia y el límite de throughput de la línea base vienen del **fan-out de 12 consultas por lectura**. Cada consulta cuesta un viaje de red, ejecución en Cassandra y deserialización en el cliente. Si cada lectura se reduce a una sola operación sobre un muro ya armado, la latencia de lectura tiene que bajar y la CPU de Cassandra también.

**Pregunta complementaria (RF7):** ¿ese costo está en Cassandra o en el cliente? Para separarlo:
- se registra la latencia **vista por Cassandra** (`nodetool proxyhistograms`, por consulta individual);
- se repite la línea base con el doble de procesos generadores. Si el throughput sube, el cliente era parte del límite.

### Prueba y resultado

| | `base_20261029-212927` (3 procesos) | `base_20261029-213317` (6 procesos) |
|---|---:|---:|
| Throughput (ops/s) | 819,0 | 1 087,9 (**+33 %**) |
| Lectura del muro p50 / p99 (ms, cliente) | 9,78 / 57,57 | 8,06 / 29,88 |
| Consulta individual en Cassandra p50 / p99 (ms, servidor) | 0,060 / 1,109 | 0,086 / 1,331 |
| CPU Cassandra / CPU generador | 129 % / 192 % | 190 % / 274 % |
| Integridad | OK (25 804 escrituras) | OK (34 166 escrituras) |

**Interpretación:**
- Una consulta tarda ~0,06 ms dentro de Cassandra (p50). Una lectura del muro tarda ~10 ms en el cliente. Aunque se sumaran las 12 consultas en serie (en realidad van en paralelo) darían menos de 1 ms. **La mayor parte del tiempo no es ejecución en Cassandra:** es el costo por consulta en el driver y en la red (serializar, enviar, recibir, deserializar 12 respuestas y ordenarlas en Python con el GIL).
- Con más procesos generadores el throughput sube y Cassandra trabaja más (129 % → 190 %) sin degradarse. Con 3 procesos, **el generador era parte del límite** de la línea base.
- H1 se sostiene igual: el costo es **por consulta**, y el fan-out de 12 lo multiplica tanto en el cliente como en Cassandra. Reducir las consultas por lectura ataca las dos partes.

Limitación: `proxyhistograms` usa histogramas con decaimiento, que reflejan sobre todo los últimos minutos. Se toma al final de cada corrida y está en el JSON (`cassandra_proxyhistograms`). Las 4 corridas principales son anteriores a que se agregara esta medición.

## 2. Optimización: muro precomputado en Redis

| Aspecto | Detalle |
|---|---|
| Problema | Fan-out de 12 consultas por lectura del muro (H1) |
| Cambio | Cada partido tiene una lista de Redis `muro:<partido>` con los últimos 100 comentarios en JSON. **Lectura:** `LRANGE muro:P-001 0 19`, 1 operación. **Escritura:** los 2 INSERT en Cassandra igual que antes, y después `LPUSHX` + `LTRIM 0 99` en un pipeline. **Miss:** si el muro no existe (frío o vencido), se arma desde Cassandra con la lectura de la línea base. Un lock `SET lock:muro:<p> NX EX 2` evita que varios hilos lo reconstruyan a la vez. **TTL:** 60 s, que acota cuánto puede quedar desactualizado |
| Archivos | `scripts/comun.py` (`leer_muro_redis`), `scripts/ejecutar_carga.py` (`publicar`, modo `optimizado`) |
| Por qué `LPUSHX` y no `LPUSH` | `LPUSH` sobre un muro vencido crearía una lista de 1 elemento y el muro se mostraría casi vacío. Con `LPUSHX` solo la lectura crea el muro, y siempre completo desde Cassandra |
| Fuente de verdad | Sigue siendo Cassandra. Redis es una proyección descartable: si se pierde, se reconstruye |
| Costo o riesgo | Ver Trade-offs |

## 3. Repetición

Mismo escenario que la línea base: 50 usuarios, 3 procesos, 30 + 120 s, 80/20, misma semilla, mismo keyspace y mismos datos iniciales. Diferencias declaradas:
- antes de cada corrida optimizada se borran las claves `muro:*` para arrancar con Redis frío (la línea base tampoco tiene nada precalculado);
- en la variante de capacidad (lazo cerrado), el modo optimizado hace muchas más operaciones, **escrituras incluidas** (207 936 contra 14 592). No es la misma carga: por eso la comparación principal es la de carga fija.

## 4. Comparación (mediciones reales)

### Carga fija: 500 ops/s ofrecidas (comparación principal)

`base_20261029-212119` contra `optimizado_20261029-212501`. Latencias en ms medidas por el cliente.

| Métrica | Línea base | Optimizado | Variación |
|---|---:|---:|---:|
| Throughput logrado (ops/s) | 498,0 | 500,0 | +0,4 % |
| Errores | 0 | 0 | – |
| Lectura p50 | 14,70 | 1,67 | **−88,6 %** |
| Lectura p95 | 31,78 | 11,10 | −65,1 % |
| Lectura p99 | 58,83 | 17,57 | −70,1 % |
| Lectura max | 181,86 | 77,02 | −57,6 % |
| Escritura p50 | 11,70 | 5,63 | −51,9 % |
| Escritura p99 | 54,45 | 22,02 | −59,6 % |
| CPU Cassandra (prom.) | 77 % | 15,5 % | **−80 %** |
| CPU Redis (prom.) | 0,2 % | 4,3 % | sube |
| Memoria Redis | ~10 MiB | ~9,8 MiB | sin cambio visible (64 muros × 100 comentarios ≈ 1-2 MiB) |
| CPU del generador | 100 % | 38,9 % | −61 % |
| Cache hits / misses | – | 47 727 / 168 | 99,6 % hits |

Las escrituras **también** mejoran aunque hacen más trabajo (Cassandra + Redis): Cassandra y el cliente quedan mucho menos cargados porque ya no atienden 4 800 consultas/s de lectura.

### Capacidad, sin pausa (complementaria)

`base_20261029-211153` contra `optimizado_20261029-211547`. Tabla completa en [evidencia/comparacion_capacidad.md](evidencia/comparacion_capacidad.md).

| Métrica | Línea base | Optimizado |
|---|---:|---:|
| Throughput (ops/s) | 484,5 (819,0 en la repetición) | 6 737,3 |
| Lectura p50 / p99 (ms) | 72,35 / 249,35 (9,78 / 57,57 en la repetición) | 0,98 / 9,36 |
| Escritura p50 / p99 (ms) | 69,74 / 245,91 | 3,35 / 18,93 |
| Escritura **max** (ms) | 521,13 | 617,76 (**regresión**) |
| CPU Cassandra / Redis | 122 % / 1 % | 90 % / 34 % |

Contra cualquiera de las dos líneas base, el throughput optimizado es entre 8 y 14 veces mayor. El rango es amplio por la variabilidad de la línea base, así que la cifra exacta no es concluyente. Lo robusto es el orden de magnitud.

**Regresión:** la latencia **máxima** de escritura empeora en la prueba de capacidad. El sistema optimizado escribe 14 veces más comentarios (≈1 350 escrituras/s contra ≈100), y algunas escrituras sufren pausas de Cassandra, probablemente flush o GC (no verificado). El p99 en cambio mejora, así que la regresión afecta a operaciones aisladas.

## 5. Trade-offs

| Costo | Detalle | Evidencia |
|---|---|---|
| **Frescura y consistencia eventual** | Un comentario escrito mientras el muro se reconstruye puede no aparecer hasta la próxima reconstrucción (≤ 60 s) | Validación: 2 comentarios aceptados ausentes del muro al final de `optimizado_20261029-212501` (están en Cassandra) |
| **Duplicación** | El mismo comentario vive en 3 lugares: 2 tablas de Cassandra y Redis | 64 muros × 100 = 6 400 copias |
| **Memoria** | ~100 comentarios × 64 partidos ocupan pocos MiB. Con 48 selecciones y 104 partidos sigue siendo chico, pero comparte los 256 MB de Redis con sesiones y caché (Hito 7) y `volatile-lru` puede desalojar muros | Memoria Redis estable en ~10 MiB |
| **Escritura más cara** | Cada comentario suma un viaje a Redis. Si Redis falla después de Cassandra, el comentario queda aceptado pero el muro desactualizado hasta que venza | No ocurrieron errores de Redis en las corridas |
| **Complejidad** | Lock de reconstrucción, `LPUSHX` y TTL: tres decisiones que hay que entender y mantener. Una versión ingenua (sin lock o con `LPUSH`) genera muros duplicados o incompletos | Validación: 0 duplicados en 12 692 elementos |
| **Costo operativo** | Un componente más en el camino crítico de la lectura | – |

## 6. Decisión

**Se adopta el muro en Redis** para la lectura en vivo de partidos con mucho tráfico. Con la misma carga redujo el p50 de lectura un 89 %, el p99 un 70 % y la CPU de Cassandra un 80 %, sin errores ni pérdida de datos. Se acepta un retraso de hasta 60 s en casos puntuales, que es razonable para un muro de comentarios.

Cassandra sigue siendo la fuente de verdad y no se cambia su modelo: el sharding por minuto sigue sirviendo para repartir las escrituras.

**Próximos pasos:**
- repetir cada configuración 3 o más veces para medir la variabilidad;
- probar el generador en otra máquina, para sacar al cliente de la ecuación;
- evaluar `LOGGED BATCH` para las 2 tablas de Cassandra y medir su costo;
- refrescar el TTL del muro en cada escritura en lugar de dejarlo vencer cada 60 s.

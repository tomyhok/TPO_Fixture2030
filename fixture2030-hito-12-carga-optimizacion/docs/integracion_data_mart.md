# Integración analítica: Data Mart de actividad por minuto

> Es una **propuesta de diseño**. No se implementó ni se midió el ETL. Lo único medido en este hito es el flujo operacional del muro.

## 1. Pregunta analítica

**¿Cómo se relaciona la actividad de los hinchas (comentarios) con lo que pasa en la cancha (tiros, posesión, audiencia), minuto a minuto y según el equipo que apoyan?**

Ejemplos de uso: "¿cuántos comentarios más se generan en el minuto posterior a un tiro?", "¿qué selección tiene la hinchada más activa en relación con su audiencia?".

## 2. Fuentes operacionales

| Fuente | Hito | Qué aporta | Clave original |
|---|---|---|---|
| Cassandra `comentarios_por_partido` | 6 | Cantidad de comentarios, usuarios distintos, equipo apoyado | `id_partido` = `P-001`, `ventana` = `AAAAMMDDHHMM`, `equipo_apoyado` = ISO |
| InfluxDB `estadisticas_partido` | 8 | Tiros, pases, posesión y usuarios activos por segundo | `partido_id` = `M001`, `equipo_id` = `EQ001_1` |
| MongoDB `equipos` | 4 | Nombre, confederación y grupo de cada selección | `codigo_iso` |
| Neo4j `Partido` | 5 | Fecha, sede, fase, equipo local y visitante | `codigo_partido` = `P-001` |

## 3. Grano, atributos y medidas

**Grano:** una fila por **partido × minuto × equipo** (2 equipos por partido).

Tabla de hechos `hecho_actividad_minuto`:

| Columna | Tipo | Origen | Transformación |
|---|---|---|---|
| `partido_id` | clave | Cassandra / Neo4j | `P-001` directo. Influx `M001` → `P-001` vía `map_partido` |
| `minuto` | clave | Cassandra `ventana` / Influx `time` | `ventana` → timestamp de inicio del minuto; Influx `date_bin('1 minute', time)` |
| `equipo_iso` | clave | Cassandra `equipo_apoyado` / Influx `equipo_id` | Influx `EQ001_1` → ISO vía `map_equipo_partido` (local = `_1`, visitante = `_2`, según Neo4j) |
| `comentarios` | medida (suma) | Cassandra | `COUNT` de comentarios con `equipo_apoyado` = equipo, en las 4 particiones shard del minuto |
| `usuarios_distintos` | medida (no sumable) | Cassandra | Usuarios distintos en el minuto. No se puede sumar entre minutos |
| `tiros_en_minuto` | medida (suma) | Influx `tiros` | `MAX - MIN` dentro del minuto, porque el contador es acumulado (Hito 8) |
| `posesion_prom` | medida (promedio) | Influx `posesion_pct` | `AVG` en el minuto |
| `audiencia_max` | medida (máximo) | Influx `usuarios_activos` | `MAX` en el minuto |
| `completo` | control | ETL | `false` si alguna fuente no respondió para ese minuto |
| `cargado_en`, `version_etl` | procedencia | ETL | Instante de carga y versión del proceso |

Dimensiones: `dim_equipo` (Mongo: ISO, nombre, confederación, grupo) y `dim_partido` (Neo4j: fecha, sede, fase, local y visitante). Tablas de correspondencia: `map_partido` (`M001` ↔ `P-001`) y `map_equipo_partido` (`EQ001_1` ↔ ISO), armadas una vez desde Neo4j.

**Almacenamiento propuesto:** un esquema estrella en una base relacional. El volumen es chico: 64 partidos × 120 min × 2 equipos ≈ 15 400 filas para todo el torneo, y lo que se necesita son joins con dimensiones y `GROUP BY` libres, que es justo donde Cassandra es incómoda.

## 4. Flujo de actualización (ETL por micro-lotes)

```
cada 5 min durante los partidos
  1. Extraer  Cassandra: por cada partido en juego y cada minuto cerrado, leer las
              4 particiones (partido, ventana, shard). Se conocen las claves → sin full scan.
              Influx: SELECT date_bin('1 minute', time), ... WHERE partido_id = ... AND time en rango
  2. Transformar  mapear claves (map_partido, map_equipo_partido), agregar por minuto y equipo
  3. Cargar   UPSERT por (partido_id, minuto, equipo_iso) → reejecutar no duplica
  4. Validar  ver sección 6
```

| Aspecto | Decisión |
|---|---|
| Frecuencia | Cada 5 minutos mientras haya partidos en juego, más un reproceso final 1 h después del partido |
| Ventana procesada | Minutos cerrados hace al menos 2 min. Cada corrida **reprocesa los últimos 10 minutos** |
| Retraso aceptable | Hasta ~7 minutos (5 de frecuencia + 2 de margen). Es una pregunta analítica: no compite con el muro en vivo |
| Datos tardíos | Los que llegan dentro de los 10 min entran en el reproceso. Los posteriores entran en el reproceso final |
| Duplicados | En Cassandra no hay, porque `id_comentario` es la clave primaria (validado en este hito). En el mart, el UPSERT por clave natural hace que el ETL sea idempotente |
| Faltantes o falla parcial | Hay una marca de agua (watermark) por fuente. Si InfluxDB falla, los minutos se cargan con las medidas de Cassandra y `completo = false`, y la marca de Influx no avanza: la corrida siguiente los completa |

## 5. Procedencia

Cada fila guarda `cargado_en` y `version_etl`. Cada medida tiene una única fuente documentada en la tabla de la sección 3. Las correspondencias de claves están en tablas explícitas, no en el código.

## 6. Validación de conteos y agregados

- Para cada partido, `SUM(comentarios)` del mart tiene que coincidir con el `COUNT(*)` de sus particiones en Cassandra (mismo control que `validar_integridad.py`).
- El `tiros_en_minuto` acumulado al final del partido tiene que coincidir con el último valor de `tiros` en Influx.
- No puede haber minutos fuera de 0-130 ni equipos que no estén en `dim_equipo`. Si un partido tiene minutos sin fila, se los reporta.

## 7. Consultar las fuentes operacionales o consultar la proyección

Responder la pregunta "en vivo" para todo el torneo, sin mart, requeriría:
- Cassandra: 64 partidos × 120 ventanas × 4 shards = **30 720 lecturas de partición**, cada vez que alguien pregunta;
- InfluxDB: 128 series agregadas por minuto;
- MongoDB y Neo4j para los nombres, más el cruce de claves distintas en el código de la aplicación.

Sería consultar 4 fuentes en serie por cada request, que es el antipatrón que menciona el enunciado. Además competiría por la misma CPU de Cassandra que en la línea base ya trabaja a más del 120 % sirviendo el muro. Con el mart, la misma pregunta es **una** consulta SQL sobre ~15 000 filas. El precio es un retraso de hasta ~7 minutos y un proceso más que mantener.

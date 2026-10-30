# Comparación con una estructura relacional

> **Análisis conceptual, no medido.** No se ejecutó una base relacional con la misma carga. Los únicos números medidos son los de Cassandra y Redis ([linea_base.md](linea_base.md), [hipotesis_y_optimizacion.md](hipotesis_y_optimizacion.md)).

## 1. Modelo relacional para el muro de comentarios

Unidad de información: **una fila por comentario**, en una sola tabla normalizada.

```sql
CREATE TABLE comentarios (
    id_comentario  uuid PRIMARY KEY,
    id_partido     text NOT NULL REFERENCES partidos(id_partido),
    id_usuario     text NOT NULL REFERENCES usuarios(id_usuario),
    equipo_apoyado char(3),
    texto          text NOT NULL,
    estado         text NOT NULL DEFAULT 'publicado',
    creado_en      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_muro      ON comentarios (id_partido, creado_en DESC);  -- lectura del muro
CREATE INDEX ix_historial ON comentarios (id_usuario, creado_en DESC);  -- historial del usuario
```

## 2. Operaciones del flujo

| Operación | Cassandra (medido) | Relacional (conceptual) |
|---|---|---|
| Leer muro | 12 consultas (3 ventanas × 4 shards), unión y orden en el cliente | `SELECT ... WHERE id_partido = $1 ORDER BY creado_en DESC LIMIT 20`: **1 consulta**, recorrido del índice `ix_muro` |
| Publicar | 2 INSERT (tabla por partido + tabla por usuario) | 1 INSERT, que actualiza 2 índices |
| Historial de usuario | Tabla duplicada `comentarios_por_usuario` | Mismo dato, otro índice: sin duplicación |
| Join con usuario o partido | No existe; el alias se desnormaliza en la fila | `JOIN` directo |

## 3. Garantías

- **Relacional:** el INSERT es atómico. El comentario y sus índices quedan juntos o no queda nada, y las FK impiden comentarios de partidos inexistentes. El muro ve el comentario apenas se hace el commit (consistencia fuerte en una sola instancia).
- **Cassandra:** cada INSERT es atómico por partición, pero las **dos tablas no se escriben en una transacción**. Si falla la segunda, queda escrito a medias. Por eso `validar_integridad.py` controla "rechazadas escritas parcialmente" (resultado: 0 en las corridas). Un `LOGGED BATCH` lo garantizaría, a costa de latencia.
- **Redis (optimizado):** el muro es una copia con consistencia eventual. Puede faltar un comentario recién aceptado hasta que vence el TTL (ver validación de frescura).

## 4. Crecimiento de volumen y concurrencia

- **Relacional:** todas las escrituras de un partido caliente van al mismo extremo del índice `(id_partido, creado_en)`, lo que genera contención en las mismas páginas. Hay un único nodo primario para escribir: se escala verticalmente, las lecturas se pueden derivar a réplicas (con retraso) y la tabla se puede particionar por fecha. Con decenas de millones de filas sigue respondiendo bien gracias al índice, pero el límite es la tasa de escritura de un solo primario.
- **Cassandra:** las escrituras se reparten en particiones `(partido, minuto, shard)` y se escala agregando nodos. A cambio, la lectura del muro se vuelve más cara (más particiones), y eso es justo lo que se midió como cuello de botella.

## 5. Qué parte del flujo es más simple o más compleja

| | Más simple en relacional | Más simple en Cassandra |
|---|---|---|
| Lectura del muro | ✔ una consulta indexada | |
| Historial y consultas nuevas | ✔ un índice o una consulta nueva, sin rediseñar | |
| Ráfagas de escritura masivas | | ✔ sin punto único de escritura |
| Moderación con transacciones (cambiar estado y auditar) | ✔ | |
| Disponibilidad ante caída de un nodo | | ✔ replicación multi-nodo nativa |

## 6. Cuándo conviene cada una (para este caso)

- **Relacional conviene** si la tasa de escritura cabe en un primario (del orden de miles de inserts por segundo con buen hardware), si importan la moderación transaccional y las FK, o si las consultas cambian seguido. Por ejemplo, la fase de grupos con partidos simultáneos de audiencia moderada.
- **Cassandra conviene** si los picos de escritura de un partido masivo superan a un primario, si se necesita alta disponibilidad multi-nodo, y si los patrones de acceso son fijos y conocidos (el muro y el historial).
- En los dos casos, un **muro precomputado en Redis** resuelve la lectura caliente. La elección de la base primaria se decide por las escrituras y las garantías, no por la lectura del muro.

## 7. Qué no se pudo medir

- Latencia y throughput de una base relacional con esta carga. No se montó PostgreSQL ni otro motor equivalente.
- El comportamiento multi-nodo: Cassandra corre en 1 nodo con RF = 1, sin costos de replicación ni de quórum.
- La contención real del índice relacional con miles de escrituras por segundo en un mismo partido.

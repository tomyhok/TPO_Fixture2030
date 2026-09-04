# Documento de Decisiones Técnicas y Evidencia — Módulo Documental Fixture 2030

Este documento consolida las decisiones de diseño del modelo de datos y la evidencia de ejecución del Hito 4 del proyecto Fixture 2030, implementado en MongoDB 7.0.

---

## PARTE I: MODELO DE DATOS Y DECISIONES TÉCNICAS

### 1. Tabla Obligatoria de Decisiones de Diseño (Exigida por Rúbrica Hito 4)

| Decisión | Alternativas consideradas | Elección | Justificación técnica | Impacto esperado |
|---|---|---|---|---|
| **Relación equipo–jugador** | 1. Embeber jugadores dentro del documento de equipo.<br>2. Referencias normalizadas (`codigo_equipo` apuntando a `codigo_iso`). | **Referencias (Modelado Híbrido)** | Los planteles contienen 23 a 26 jugadores (más de 1.400 en el torneo) y sufren actualizaciones continuas (goles, tarjetas, estado de salud) independientes de la información estática del país. Embeber generaría documentos pesados, fragmentación por crecimiento dinámico y riesgo de alcanzar el límite BSON de 16MB. Las estadísticas se embeben en el jugador porque siempre se consultan y mutan juntas. | Consultas de jugadores rápidas y atómicas; actualizaciones sin bloqueos a nivel de equipo; agregaciones limpias vía `$lookup` solo cuando se requiere consolidar información. |
| **Validación documental** | 1. Esquema flexible sin validación.<br>2. Validación exclusiva en capa de aplicación.<br>3. `$jsonSchema` estricto a nivel de base de datos (`validationLevel: "strict"`, `validationAction: "error"`). | **`$jsonSchema` estricto en MongoDB** | Garantiza la integridad estructural y de tipos directamente en el motor, evitando que scripts erróneos o accesos concurrentes inserten dorsales fuera de rango (1-99), códigos ISO malformados o confederaciones inexistentes. | Detección inmediata de inconsistencias en tiempo de inserción/modificación (RNF3); no depende del lenguaje del cliente que se conecte. |
| **Estrategia de identificadores** | 1. Claves autogeneradas `ObjectId` de BSON.<br>2. Claves naturales de negocio compuestas y legibles. | **Claves Naturales Semánticas** (`_id` / `codigo_iso` FIFA para equipos, y `EQUIPO-DORSAL` para jugadores). | El código FIFA/ISO de 3 letras (ej. `"ARG"`) ya es único, inmutable y universalmente reconocido en el dominio deportivo. Para los jugadores, la tupla equipo + dorsal identifica unívocamente a cada atleta en el fixture (ej. `"ARG-10"`). | Elimina la necesidad de índices secundarios redundantes para búsquedas primarias; facilita lecturas directas y simplifica URLs y logs de auditoría. |
| **Índices principales** | 1. Sin índices (depender exclusivamente de `_id`).<br>2. Índices individuales exhaustivos en todos los campos.<br>3. Índices específicos de alta selectividad y compuestos alineados a las consultas críticas. | **Índices Específicos Selectivos y Compuestos** (`idx_codigo_iso_unico`, `idx_codigo_equipo`, `idx_equipo_posicion`, `idx_ranking`, `idx_grupo`, `idx_goles`, `idx_dorsal_unico`). | Cada índice responde a un patrón de consulta real del negocio (búsqueda por grupo, ranking paginado, filtrado por posición, tabla de goleadores). Un índice no es gratis: consume memoria RAM (WiredTiger) y penaliza escrituras. | Las consultas críticas pasan de escaneo completo (`COLLSCAN` en O(N)) a búsqueda en árbol B+ (`IXSCAN` en O(log N)), reduciendo el tiempo de respuesta a < 1 ms (RNF4). |
| **Carga y actualización** | 1. Inserción simple documento a documento (`insertOne`).<br>2. Inserción masiva no idempotente (`insertMany`).<br>3. Operación por lotes idempotente con `bulkWrite` + `replaceOne` + `upsert: true`. | **`bulkWrite` con `replaceOne` y `upsert: true`** | Permite reejecutar el script de carga (`02-carga.js`) tantas veces como sea necesario sin duplicar información ni fallar por colisión de claves únicas. Minimiza los viajes de ida y vuelta de red (*roundtrips*). | Carga reproducible y segura (RF8, RNF1); cero duplicados y tiempos de carga masiva de los 64 equipos y 1472 jugadores en menos de 1 segundo. |

### 2. Definición de Colecciones y Esquemas

La base de datos `fixture2030` contiene dos colecciones principales: `equipos` y `jugadores`.

#### Colección: `equipos`
Almacena la identidad deportiva, jerárquica y de clasificación de cada una de las 64 selecciones participantes:
```json
{
  "_id": "ARG",
  "codigo_iso": "ARG",
  "nombre": "Argentina",
  "confederacion": "CONMEBOL",
  "grupo": "A",
  "director_tecnico": "Lionel Scaloni",
  "ranking_fifa": 1,
  "pais_anfitrion": true
}
```

#### Colección: `jugadores`
Almacena la ficha personal y deportiva de los futbolistas convocados, vinculados a su selección mediante `codigo_equipo`:
```json
{
  "_id": "ARG-10",
  "nombre": "Lionel Messi",
  "dorsal": 10,
  "posicion": "DEL",
  "fecha_nacimiento": "1987-06-24",
  "altura_cm": 170,
  "pie_habil": "izquierdo",
  "codigo_equipo": "ARG",
  "equipo_id": "ARG",
  "estado": "Convocado",
  "estadisticas": {
    "partidos": 180,
    "goles": 106,
    "asistencias": 56
  }
}
```

### 3. Justificación de Referencias vs. Embebed (Embedding)

Para representar la relación 1:N entre selecciones y jugadores, se analizó profundamente el trade-off entre:

1. **Documentos Embebidos (Embedding)**:
   - *Ventajas teóricas*: Lectura de la selección y su plantel completo en una sola operación sin JOINs; atomicidad dentro del documento.
   - *Desventajas críticas en este dominio*:
     - Un plantel cuenta con entre 23 y 26 futbolistas, y el seguimiento de eventos durante el Mundial (goles, asistencias, tarjetas, sustituciones) genera una alta tasa de escrituras concurrentes. Modificar las estadísticas de un delantero obligaría a bloquear y reescribir todo el documento del equipo (amplificación de I/O).
     - Dificultad para responder consultas independientes sobre jugadores, tales como la tabla global de goleadores del torneo o el filtrado de defensores por confederación, requiriendo complejas operaciones `$unwind` en memoria.
     - Riesgo de crecimiento no acotado hacia el límite BSON de 16MB.

2. **Referencias con Subdocumentos Embebidos (Estrategia Elegida)**:
   - La relación **Equipo - Jugador** se desacopla mediante **referencias documentales** (`jugadores.codigo_equipo` -> `equipos.codigo_iso`).
   - Las **estadísticas deportivas individuales** se mantienen **embebidas** en el jugador (`estadisticas: { partidos, goles, asistencias }`), ya que su ciclo de vida y lectura es 100% cohesionado con el futbolista.
   - Cuando se requiere consolidar información agregada del torneo (ej. rendimiento goleador por confederación), se utiliza el operador nativo `$lookup`, optimizado mediante el índice en `codigo_equipo`.

### 4. Estrategia de Validación e Integridad

Los esquemas en `schemas/equipos.schema.js` y `schemas/jugadores.schema.js` implementan las siguientes restricciones mediante `$jsonSchema`:
- **Tipos y Formatos**: Strings para identificadores, enteros estrictos para métricas numéricas (`ranking_fifa`, `dorsal`, `altura_cm`).
- **Restricciones de Dominio (Enums)**:
  - `confederacion`: `["CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"]`.
  - `posicion`: `["ARQ", "DEF", "MED", "DEL", "Arquero", "Defensor", "Mediocampista", "Delantero"]`.
  - `grupo`: Letras de la `"A"` a la `"P"`.
- **Límites de Negocio**: `dorsal` acotado estrictamente entre 1 y 99; `ranking_fifa` con valor mínimo 1.
- **Integridad Deportiva**: Se establece un índice único compuesto sobre `{ codigo_equipo: 1, dorsal: 1 }`, impidiendo que dos jugadores de la misma selección porten el mismo número de camiseta.

### 5. Trazabilidad con Hitos Anteriores

- **Vínculo con el Hito 2 (Matriz de Selección)**: En el Hito 2 se seleccionó MongoDB para el almacenamiento de selecciones y futbolistas debido a la flexibilidad de sus perfiles semi-estructurados y la capacidad de evolucionar atributos (lesiones, trayectoria de clubes, estadísticas avanzadas) sin migraciones destructivas de DDL.
- **Vínculo con el Hito 3 (Arquitectura Distribuida)**: En el Hito 3 se definió un modelo CP con tolerancia a particiones de red y consistencia fuerte para el estado de la competición. Los campos `confederacion` y `grupo` actúan como claves naturales de particionamiento (*shard keys*) para escenarios de sharding horizontal por zonas geográficas. Asimismo, el requisito de latencia menor a 100 ms para consultas críticas queda garantizado mediante los índices secundarios en B-Tree verificados mediante `explain()`.

---

## PARTE II: EVIDENCIA DE PRUEBAS Y RENDIMIENTO (RF13, RNF4)

Salidas verificadas de la ejecución del módulo en MongoDB 7.0.

### 1. Inicio y Creación Automática de Colecciones (RF1, RF3, RF7)

Al levantar el contenedor por primera vez, MongoDB ejecuta los scripts de `init-scripts/` en orden.

```bash
$ docker compose up -d
$ docker compose logs mongodb
=== Creando colecciones con esquemas de validación estricta ===
Colección 'equipos' creada exitosamente con validación $jsonSchema.
Colección 'jugadores' creada exitosamente con validación $jsonSchema.
=== Iniciando carga reproducible de datos ===
equipos: 64 insertados, 0 actualizados.
jugadores: 1472 insertados, 0 actualizados.

Equipos cargados:   64 (Objetivo RF4: 64)
Jugadores cargados: 1472 (Objetivo RF5: >= 1000)
Jugadores sin equipo valido (huerfanos): 0
```

### 2. Índices Creados (RF12)

Salida de `03-indices.js` con los índices requeridos y de soporte:

```text
=== Creando índices para 'equipos' ===
=== Creando índices para 'jugadores' ===

Índices creados en 'equipos':
  _id_ -> {"_id":1}
  idx_codigo_iso_unico -> {"codigo_iso":1}
  idx_grupo -> {"grupo":1}
  idx_ranking -> {"ranking_fifa":1}

Índices creados en 'jugadores':
  _id_ -> {"_id":1}
  idx_codigo_equipo -> {"codigo_equipo":1}
  idx_equipo_posicion -> {"codigo_equipo":1,"posicion":1}
  idx_equipo_id_posicion -> {"equipo_id":1,"posicion":1}
  idx_goles -> {"estadisticas.goles":-1}
  idx_dorsal_unico -> {"codigo_equipo":1,"dorsal":1}
```

### 3. Carga Reproducible e Idempotencia (RF8, RNF1, RNF3)

Al reejecutar la carga sobre la base ya poblada, `bulkWrite` realiza *upserts* sin generar duplicados:

```bash
$ docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
    fixture2030 --file /docker-entrypoint-initdb.d/02-carga.js
=== Iniciando carga reproducible de datos ===
equipos: 0 insertados, 0 actualizados.
jugadores: 0 insertados, 0 actualizados.

Equipos cargados:   64 (Objetivo RF4: 64)
Jugadores cargados: 1472 (Objetivo RF5: >= 1000)
Jugadores sin equipo valido (huerfanos): 0
```

### 4. Persistencia de Datos (RF2, RNF2)

Reinicio del contenedor y comprobación de volumen `mongodb_data`:

```bash
$ docker compose restart
$ docker compose exec mongodb mongosh -u admin -p password123 --authenticationDatabase admin \
    fixture2030 --eval 'print("Equipos:", db.equipos.countDocuments(), "Jugadores:", db.jugadores.countDocuments())'
Equipos: 64 Jugadores: 1472
```

### 5. Operaciones de Inserción, Rechazo y Actualización Controlada (RF9)

Salida de `queries/01-operaciones.js`:

```text
==================================================
 1. INSERCIÓN DE NUEVO EQUIPO (VALIDADA)
==================================================
Equipo 'ITA' insertado exitosamente cumpliendo $jsonSchema.
{
  _id: 'ITA',
  codigo_iso: 'ITA',
  nombre: 'Italia',
  confederacion: 'UEFA',
  grupo: 'P',
  director_tecnico: 'Luciano Spalletti',
  ranking_fifa: 9,
  pais_anfitrion: false
}

==================================================
 2. DEMOSTRACIÓN DE VALIDACIÓN ESTRICTA (RECHAZO)
==================================================
ÉXITO: El motor MongoDB rechazó el documento por violación de esquema ($jsonSchema):
  -> Document failed validation

==================================================
 3. INSERCIÓN DE NUEVO JUGADOR (VALIDADO)
==================================================
Jugador 'ARG-24' insertado exitosamente cumpliendo $jsonSchema.
{
  _id: 'ARG-24',
  nombre: 'Martin Solari',
  dorsal: 24,
  posicion: 'DEL',
  fecha_nacimiento: '2003-05-14',
  altura_cm: 180,
  pie_habil: 'derecho',
  codigo_equipo: 'ARG',
  equipo_id: 'ARG',
  estado: 'Convocado',
  estadisticas: { partidos: 0, goles: 0, asistencias: 0 }
}

==================================================
 4. ACTUALIZACIÓN CONTROLADA DE EQUIPO ($set)
==================================================
Equipo ARG actualizado con $set:
{
  _id: 'ARG',
  codigo_iso: 'ARG',
  nombre: 'Argentina',
  confederacion: 'CONMEBOL',
  grupo: 'A',
  director_tecnico: 'Lionel Scaloni',
  ranking_fifa: 1,
  pais_anfitrion: true
}

==================================================
 5. ACTUALIZACIÓN CONTROLADA DE JUGADOR ($set e $inc)
==================================================
Jugador ARG-24 actualizado:
{
  _id: 'ARG-24',
  nombre: 'Martin Solari',
  codigo_equipo: 'ARG',
  estado: 'Convocado',
  club_actual: 'Inter Miami',
  estadisticas: { partidos: 1, goles: 1, asistencias: 0 }
}
```

### 6. Consultas de Recuperación (RF10)

Salida de `queries/02-consultas.js`:

```text
==================================================
 1. IDENTIFICACIÓN DIRECTA (Por Clave)
==================================================
a) Equipo con codigo_iso 'ARG':
{
  _id: 'ARG',
  ...
}

b) Jugador con _id 'ARG-10':
{
  _id: 'ARG-10',
  ...
}

==================================================
 2. FILTRADO (Por condición de negocio)
==================================================
Equipos clasificados en el Grupo A:
  [ARG] Argentina (CONMEBOL) - Ranking FIFA: #1
  [NED] Países Bajos (UEFA) - Ranking FIFA: #7
  [ROU] Rumania (UEFA) - Ranking FIFA: #43
  [IRN] Irán (AFC) - Ranking FIFA: #20

==================================================
 3. FILTRADO + PROYECCIÓN
==================================================
Defensores de Brasil (BRA), proyectando solo nombre, dorsal, posición y altura:
  #4 Marquinhos (DEF) - 183 cm
  ...

==================================================
 4. ORDENAMIENTO (Top 10 Goleadores del Torneo)
==================================================
Top 10 jugadores ordenados descendentemente por cantidad de goles:
  1. Julián Álvarez (ARG) - 15 goles
  ...

==================================================
 5. PAGINACIÓN (Equipos por Ranking FIFA)
==================================================
Equipos ordenados por ranking - Página 2 (10 por página, skip 10):
  #11. España (ESP) - UEFA
  ...
```

### 7. Agregación de Negocio (RF11)

Salida de `queries/03-agregacion.js`:

```text
================================================================================
 REPORTE CONSOLIDADO: RENDIMIENTO GOLEADOR Y PLANTELES POR CONFEDERACIÓN (RF11)
================================================================================
Confederación: UEFA
  • Plantel consolidado:  552 jugadores
  • Goles totales:        2640
  • Promedio por jugador: 4.78 goles/jugador
  • Récord individual:    14 goles
------------------------------------------------------------------
...
```

### 8. Análisis de Rendimiento con `explain()`: Comparativa Antes vs. Después (RF13, RNF4)

Salida de `queries/04-explain.js`:

```text
================================================================================
 EXPERIMENTO DE RENDIMIENTO: CONSULTA CRÍTICA ANTES Y DESPUÉS DEL ÍNDICE
================================================================================
Consulta analizada: Filtrar defensores de un equipo:
  db.jugadores.find({ codigo_equipo: 'BRA', posicion: 'DEF' })

>>> ESTADO 1: ANTES de crear el índice (COLLSCAN)
  ├─ Etapa de ejecución:   COLLSCAN
  ├─ Índice utilizado:     ninguno (Full Collection Scan)
  ├─ Documentos devueltos: 7
  ├─ Documentos examinados:1472
  ├─ Claves examinadas:    0
  └─ Tiempo de ejecución:  2 ms

>>> CREANDO ÍNDICE: db.jugadores.createIndex({ codigo_equipo: 1, posicion: 1 }, { name: 'idx_equipo_posicion' })...
Índice creado exitosamente.

>>> ESTADO 2: DESPUÉS de crear el índice (IXSCAN)
  ├─ Etapa de ejecución:   IXSCAN
  ├─ Índice utilizado:     idx_equipo_posicion
  ├─ Documentos devueltos: 7
  ├─ Documentos examinados:7
  ├─ Claves examinadas:    7
  └─ Tiempo de ejecución:  0 ms

--------------------------------------------------------------------------------
 TABLA COMPARATIVA DE EFICIENCIA (RNF4):
--------------------------------------------------------------------------------
 Métrica                | Antes (Sin Índice)          | Después (Con Índice)
------------------------|-----------------------------|-------------------------
 Etapa de escaneo       | COLLSCAN (Barrido total)    | IXSCAN + FETCH (B-Tree)
 Documentos examinados  | 1472 documentos             | 7 documentos (Ratio 1:1)
 Claves examinadas      | 0                           | 7
 Complejidad temporal   | O(N)                        | O(log N)
--------------------------------------------------------------------------------
```


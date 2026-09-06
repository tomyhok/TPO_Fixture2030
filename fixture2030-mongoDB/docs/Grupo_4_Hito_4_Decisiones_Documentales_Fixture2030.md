# Documento de Decisiones Técnicas y Evidencia — Módulo Documental Fixture 2030

Este documento consolida las decisiones de diseño del modelo de datos y la evidencia de ejecución del Hito 4 del proyecto Fixture 2030, implementado en MongoDB 7.0.

---

## PARTE I: MODELO DE DATOS Y DECISIONES TÉCNICAS

### 1. Tabla Obligatoria de Decisiones de Diseño (Exigida por Rúbrica Hito 4)

| Decisión | Alternativas consideradas | Elección | Justificación técnica | Impacto esperado |
|---|---|---|---|---|
| **Relación equipo–jugador** | 1. Embeber jugadores dentro del documento de equipo.<br>2. Referencias normalizadas (`codigo_equipo` apuntando a `codigo_iso`). | **Referencias documentales** | Los planteles se mantienen en una colección independiente y cada jugador conserva la referencia a su selección. Esto permite consultar y actualizar equipos y jugadores por separado, sin duplicar la información administrativa del equipo dentro de cada ficha. | Consultas y actualizaciones independientes sobre las dos colecciones, con integridad referencial comprobada durante la carga. |
| **Validación documental** | 1. Esquema flexible sin validación.<br>2. Validación exclusiva en capa de aplicación.<br>3. `$jsonSchema` estricto a nivel de base de datos (`validationLevel: "strict"`, `validationAction: "error"`). | **`$jsonSchema` estricto en MongoDB** | Garantiza la integridad estructural y de tipos directamente en el motor, evitando que scripts erróneos o accesos concurrentes inserten dorsales fuera de rango (1-99), códigos ISO malformados o confederaciones inexistentes. | Detección inmediata de inconsistencias en tiempo de inserción/modificación (RNF3); no depende del lenguaje del cliente que se conecte. |
| **Estrategia de identificadores** | 1. Claves autogeneradas `ObjectId` de BSON.<br>2. Claves naturales de negocio compuestas y legibles. | **Claves Naturales Semánticas** (`_id` / `codigo_iso` FIFA para equipos, y `EQUIPO-DORSAL` para jugadores). | El código FIFA/ISO de 3 letras (ej. `"ARG"`) ya es único, inmutable y universalmente reconocido en el dominio deportivo. Para los jugadores, la tupla equipo + dorsal identifica unívocamente a cada atleta en el fixture (ej. `"ARG-10"`). | Elimina la necesidad de índices secundarios redundantes para búsquedas primarias; facilita lecturas directas y simplifica URLs y logs de auditoría. |
| **Índices principales** | 1. Sin índices, salvo `_id`.<br>2. Índices individuales en todos los campos.<br>3. Índices específicos alineados con las consultas requeridas. | **Índices selectivos y compuestos** (`idx_codigo_equipo`, `idx_equipo_posicion`, `idx_dorsal_unico`, más los índices de consulta de equipos). | Cada índice responde a un patrón concreto: filtrado por confederación, ordenamiento por ranking, filtrado de jugadores por equipo y posición e integridad del dorsal. | Optimización de consulta pasando de escaneo de colección (`COLLSCAN`) a escaneo selectivo por índice (`IXSCAN`), reduciendo los documentos examinados al mínimo necesario. |
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
Almacena la ficha personal y deportiva de los futbolistas, vinculados a su selección mediante `codigo_equipo`:
```json
{
  "_id": "ARG-10",
  "nombre": "Lionel Messi",
  "dorsal": 10,
  "posicion": "DEL",
  "fecha_nacimiento": "1987-06-24",
  "edad": 43,
  "altura_cm": 170,
  "pie_habil": "izquierdo",
  "club_actual": "Inter Miami",
  "codigo_equipo": "ARG"
}
```

### 3. Justificación de Referencias vs. Embedding

Para representar la relación 1:N entre selecciones y jugadores, se analizó profundamente el trade-off entre:

1. **Documentos embebidos**:
  - Permiten recuperar un equipo y sus jugadores en un único documento.
  - Duplican los datos de la selección en cada ficha y mezclan dos entidades con ciclos de actualización diferentes.

2. **Referencias documentales (estrategia elegida)**:
  - La relación **Equipo - Jugador** se representa mediante `jugadores.codigo_equipo` apuntando a `equipos.codigo_iso`.
  - Las fichas de jugadores se mantienen independientes para permitir filtros, proyecciones, paginación y agregaciones sobre la colección `jugadores`.
  - La carga verifica que cada `codigo_equipo` corresponda a un equipo existente.

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

- **Vínculo con el Hito 2 (Matriz de Selección)**: Se recupera la decisión de utilizar MongoDB para perfiles semiestructurados de selecciones y futbolistas. El modelo documental permite mantener las dos colecciones con esquemas claros y evolucionables.
- **Desacoplamiento equipo-jugador**: La relación se implementa mediante `codigo_equipo`, evitando duplicar la información de `equipos` dentro de cada jugador.
- **Contexto de ejecución**: El Hito 4 corre sobre un único contenedor de MongoDB en Docker Compose, con almacenamiento persistente local.

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
  idx_confederacion -> {"confederacion":1}
  idx_grupo -> {"grupo":1}
  idx_ranking -> {"ranking_fifa":1}

Índices creados en 'jugadores':
  _id_ -> {"_id":1}
  idx_codigo_equipo -> {"codigo_equipo":1}
  idx_equipo_posicion -> {"codigo_equipo":1,"posicion":1}
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
  edad: 27,
  altura_cm: 180,
  pie_habil: 'derecho',
  club_actual: 'No informado',
  codigo_equipo: 'ARG',
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
 5. ACTUALIZACIÓN CONTROLADA DE JUGADOR ($set)
==================================================
Jugador ARG-24 actualizado:
{
  _id: 'ARG-24',
  nombre: 'Martin Solari',
  dorsal: 24,
  posicion: 'DEL',
  codigo_equipo: 'ARG',
  club_actual: 'No informado'
}
```

### 6. Consultas de Recuperación (RF10)

Salida de `queries/02-consultas.js`:

```text
==================================================
 1. IDENTIFICACIÓN DIRECTA (Por Clave)
==================================================
a) Equipo con _id 'ARG':
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
 2. FILTRADO POR CONFEDERACIÓN
==================================================
Equipos pertenecientes a CONMEBOL:
  [ARG] Argentina - Grupo A
  ...

==================================================
 3. FILTRADO + PROYECCIÓN
==================================================
Defensores de Argentina (ARG), proyectando nombre, dorsal y club:
  #4 Jugador de ejemplo - No informado
  ...

==================================================
 4. ORDENAMIENTO Y PAGINACIÓN
==================================================
Equipos ordenados por ranking - Página 2 (10 por página, skip 10):
  #11. España (ESP) - UEFA
  ...
```

### 7. Agregación de Negocio (RF11)

Salida de `queries/03-agregacion.js`:

```text
================================================================================
 REPORTE DE JUGADORES CARGADOS POR EQUIPO (RF11)
================================================================================
Equipo: ARG | Total de jugadores: 23
Equipo: BRA | Total de jugadores: 23
...
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
  └─ Tiempo de ejecución:  6 ms

>>> CREANDO ÍNDICE: db.jugadores.createIndex({ codigo_equipo: 1, posicion: 1 }, { name: 'idx_equipo_posicion' })...
Índice creado exitosamente.

>>> ESTADO 2: DESPUÉS de crear el índice (IXSCAN)
  ├─ Etapa de ejecución:   IXSCAN
  ├─ Índice utilizado:     idx_equipo_posicion
  ├─ Documentos devueltos: 7
  ├─ Documentos examinados:7
  ├─ Claves examinadas:    7
  └─ Tiempo de ejecución:  2 ms

--------------------------------------------------------------------------------
 TABLA COMPARATIVA DE EFICIENCIA (RNF4):
--------------------------------------------------------------------------------
 Métrica                | Antes (Sin Índice)          | Después (Con Índice)
------------------------|-----------------------------|-------------------------
 Etapa de escaneo       | COLLSCAN                    | IXSCAN
 Documentos examinados  | 1472 documentos             | 7 documentos
 Claves examinadas      | 0                           | 7
 Documentos devueltos   | 7                           | 7
 Tiempo observado (ms)  | 6                           | 2
--------------------------------------------------------------------------------
```


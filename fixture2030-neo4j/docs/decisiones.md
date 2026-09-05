# Decisiones de Diseño y Análisis Relacional

Este documento justifica las decisiones técnicas adoptadas para el desarrollo del Módulo de Grafos en Neo4j, su relación con el Módulo Documental y el análisis de la información obtenida.

## 1. Problema Relacional
El uso de una base de datos de grafos se justifica por la necesidad de resolver consultas profundamente conectadas que, en un modelo documental o relacional tradicional, requerirían múltiples operaciones de agregación complejas (`$lookup` o `JOIN`). Preguntas como *"¿Qué jugadores pisarán el césped de un estadio específico durante la fase de grupos?"* implican saltar desde la entidad Sede, pasar por Partido, bifurcarse hacia Equipo y terminar en los Jugadores individuales. Neo4j permite modelar y recorrer esta semántica de manera natural y altamente eficiente.

## 2. Consistencia y Vínculo con el Módulo Documental (Hitos 1 a 4)
Para preservar la integridad de los datos entre MongoDB y Neo4j, se adoptó la siguiente estrategia:
* **Identificadores Homologados:** Se mantuvieron los atributos `_id` naturales de los documentos de MongoDB como las claves primarias en los nodos de Neo4j (`codigo_iso` para Equipos e `id_jugador` para Jugadores).
* **Minimización de Duplicidad:** El grafo no replica datos pesados o estáticos (como fechas de nacimiento, peso o estadísticas históricas). Neo4j actúa estrictamente como un motor de navegación de relaciones, delegando la información detallada al Módulo Documental.

## 3. Integridad y Rendimiento
Para garantizar la calidad de los datos y cumplir con el requisito de idempotencia en la carga masiva, se implementaron restricciones de unicidad (`CREATE CONSTRAINT`). Estas reglas operan sobre los identificadores principales de todos los nodos (`Equipo`, `Jugador`, `Sede`, `Partido`, `Evento`). Esto previene la duplicación accidental de nodos y crea automáticamente índices B-Tree subyacentes, optimizando significativamente la velocidad de las consultas iniciales (nodos de anclaje) en los recorridos.

## 4. Análisis Relacional (Centralidad)
Para el análisis avanzado del subgrafo, se implementó una métrica basada en la **centralidad de grado** enfocada en las Sedes. 
* **Propósito:** La consulta calcula cuántas delegaciones internacionales (selecciones distintas) pasan por un mismo estadio a lo largo del fixture.
* **Interpretación para el negocio:** Identificar los "hubs logísticos" del Mundial permite a la organización focalizar recursos críticos. Un estadio con alta centralidad de selecciones distintas exige mayor planificación en seguridad internacional, alojamiento múltiple, capacidad de transporte y distribución de ingresos por turismo, en comparación con un estadio que alberga muchos partidos pero de menos equipos repetidos.
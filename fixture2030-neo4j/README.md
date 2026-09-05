# TPO Fixture 2030 - Módulo de Grafos (Neo4j)

Este directorio contiene el entorno local y los scripts de base de datos orientada a grafos para el Hito 5 del proyecto Fixture 2030 (Ingeniería de Datos II). El modelo está diseñado para analizar las relaciones deportivas, cruces de partidos y distribución de sedes mediante Neo4j.

## 📋 Requisitos Previos
* Docker y Docker Desktop (o Docker Engine).
* Haber ejecutado previamente el módulo de MongoDB (Hito 4) para contar con los archivos `equipos.json` y `jugadores.json` en la carpeta `fixture2030-mongoDB/init-scripts/data/`.

---

## 🚀 Guía de Inicio Rápido (Reproducibilidad)

Siga estos pasos exactos para levantar el entorno y cargar el subgrafo desde cero:

### 1. Iniciar el entorno
Abra una terminal en la carpeta `fixture2030-neo4j` y levante el contenedor:

```bash
docker compose up -d
```
*Nota: Este comando utiliza la imagen `neo4j:latest` y configura el plugin APOC, tal como se requiere en la especificación.*

### 2. Copiar los insumos de datos
Para garantizar la trazabilidad con el modelo documental, copie los archivos JSON del Hito 4 al volumen de importación de Neo4j. Ejecute esto desde la raíz del repositorio (`TPO_Fixture2030`):

```bash
docker cp fixture2030-mongoDB/init-scripts/data/equipos.json fixture2030-neo4j:/var/lib/neo4j/import/
docker cp fixture2030-mongoDB/init-scripts/data/jugadores.json fixture2030-neo4j:/var/lib/neo4j/import/
```

### 3. Acceder a Neo4j Browser
Ingrese a [http://localhost:7474](http://localhost:7474) en su navegador web.
Conéctese utilizando las credenciales locales definidas en el `docker-compose.yml`:
* **URL de conexión:** `neo4j://localhost:7687`
* **Usuario:** `neo4j`
* **Contraseña:** `fixture2030`

### 4. Ejecución de Scripts (Carga y Consultas)
Dentro del editor de Neo4j Browser, copie y ejecute el contenido de los archivos ubicados en la carpeta `queries/` **estrictamente en este orden**:

1. **`estructura.cypher`**: Crea las restricciones de unicidad e índices para garantizar la integridad de los identificadores.
2. **`carga.cypher`**: Ejecuta la importación masiva de nodos y relaciones de forma idempotente utilizando APOC.
3. **`crud.cypher`**: Demuestra las operaciones de creación, lectura, actualización y eliminación sobre un evento de prueba.
4. **`consultas_grafo.cypher`**: Contiene los análisis relacionales, saltos múltiples y el cálculo de centralidad de sedes.

---

## 📂 Estructura del Directorio
* `/docs`: Documentación técnica, decisiones de diseño y capturas de evidencia.
* `/import`: Volumen mapeado para la lectura de archivos JSON.
* `/queries`: Scripts Cypher organizados por propósito.
* `docker-compose.yml`: Definición del servicio y volúmenes de Neo4j.
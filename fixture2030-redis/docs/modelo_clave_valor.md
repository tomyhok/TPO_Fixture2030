# Modelo Clave/Valor y Nomenclatura

Basado en los patrones de acceso definidos, este documento describe el modelo de estructuras elegidas, sus atributos y la convención de claves (Namespace). Todas las claves son explícitas y no revelan secretos.

## Convención de Nomenclatura (Namespace)

El formato utilizado es: `<dominio>:<alcance/entidad>:<id>[:<sub-entidad>]`

*   Usamos minúsculas y separamos las partes semánticas por dos puntos (`:`).
*   Ninguna clave contiene tokens o contraseñas en su nombre visible.

---

## 1. Sesiones de Usuario
Representa el estado activo de la sesión de un hincha o administrador.

*   **Clave**: `sesion:{id_usuario}` (Ejemplo: `sesion:U1092`)
*   **Estructura**: `Hash`
*   **Atributos**:
    *   `token` (string): Identificador pseudoaleatorio generado al login (no exponer en keys).
    *   `rol` (string): Para control de acceso rápido (ej. `fan`, `admin`).
    *   `ultimo_acceso` (string, ISO8601): Timestamp de la última vez que interactuó.
*   **Motivación**: Permite a la API hacer `HGETALL` (o traer campos específicos) rápidamente, y hacer `HSET` solo del campo `ultimo_acceso` para renovar la actividad.

## 2. Caché de Ficha de Partido
Representa una instantánea (copia de solo lectura rápida) de los datos del partido procedentes de MongoDB/Neo4j.

*   **Clave**: `cache:partido:{id_partido}` (Ejemplo: `cache:partido:M001`)
*   **Estructura**: `String`
*   **Contenido**: JSON serializado.
    ```json
    {"id": "M001", "local": "ARG", "visitante": "BRA", "goles_local": 2, "goles_visitante": 0, "minuto": 85, "estado": "jugando"}
    ```
*   **Motivación**: Maximizar el throughput. Cargar 1 string con GET consume ínfimos ciclos de reloj de Redis, lo que permite abastecer picos de lectura enormes en los mundiales.

## 3. Votación "Jugador del Partido" (Concurrencia)
Representa un ranking de acumulación de votos en vivo.

*   **Clave**: `encuesta:partido:{id_partido}:figura` (Ejemplo: `encuesta:partido:M001:figura`)
*   **Estructura**: `Sorted Set` (zset)
*   **Miembros y Scores**:
    *   *Miembro*: `id_jugador` (ej. `J010`)
    *   *Score*: Número entero representando la cantidad de votos que recibió el jugador.
*   **Motivación**: El caso de concurrencia extrema (miles de personas votando por segundo al mismo jugador) causa *lost updates* si se intenta leer-sumar-guardar desde la app. Utilizar la operación atómica de servidor `ZINCRBY` sobre un Sorted Set resuelve por completo la concurrencia y mantiene el ranking `Top N` automáticamente.

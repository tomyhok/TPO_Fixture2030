# Patrones de Acceso

Antes de diseñar el modelo de claves en Redis, se identificaron los siguientes patrones de lectura y escritura prioritarios para el módulo (cumpliendo con el Requisito Funcional 2).

## 1. Validación y Gestión de Sesión
*   **Solicitante**: El middleware de autenticación de la aplicación, en nombre del usuario.
*   **Entrada para localizarlo**: El identificador de usuario (`id_usuario`).
*   **Respuesta esperada**: Atributos del estado de la sesión (ej. token de autorización válido, rol del usuario, timestamp de última actividad).
*   **Frecuencia**:
    *   *Lectura*: Extremadamente alta. Cada solicitud a una ruta protegida verificará la sesión.
    *   *Actualización (Escritura)*: Alta. Cada solicitud válida actualiza el timestamp de último acceso para renovar el ciclo de vida de la sesión.
*   **Tipo de dato**: Temporal. La fuente de verdad de las credenciales (hash de contraseña, etc.) y de la existencia real del usuario reside en la base de datos documental/relacional de usuarios. Esta sesión es estrictamente estado transitorio de autenticación.
*   **Estructura elegida**: `Hash`. Permite obtener o actualizar campos específicos (ej. actualizar solo `ultimo_acceso`) sin tener que sobrescribir el string entero de la sesión.

## 2. Lectura de Ficha Pública de un Partido
*   **Solicitante**: Los usuarios que acceden al Fixture (frontend/apps móviles).
*   **Entrada para localizarlo**: El código o ID del partido (ej. `M001`).
*   **Respuesta esperada**: La ficha completa del partido (equipos, resultado actual, estadio, formaciones).
*   **Frecuencia**:
    *   *Lectura*: Masiva, especialmente durante partidos populares donde cientos de miles de usuarios observan la misma vista.
    *   *Actualización*: Baja-Moderada (ej. un gol cada ~45 mins, cambios en estado del partido).
*   **Tipo de dato**: Copia temporal (Caché). La fuente de verdad es la base de datos documental (Neo4j/MongoDB) del Hito anterior.
*   **Estructura elegida**: `String`. Al ser de lectura masiva y en formato inmutable para la vista, se guarda el JSON completo serializado. Permite una respuesta O(1) de muy bajo costo de CPU y ancho de banda interno.

## 3. Votación "Jugador del Partido" (Concurrencia)
*   **Solicitante**: Usuarios autenticados (votando) y el sistema (mostrando ranking).
*   **Entrada para localizarlo**: El ID del partido (ej. `M001`).
*   **Respuesta esperada**: La lista de jugadores ordenada de mayor a menor según los votos acumulados en tiempo real.
*   **Frecuencia**:
    *   *Lectura*: Alta (para mostrar el estado de la encuesta).
    *   *Escritura*: Muy Alta y altamente concurrente durante los últimos minutos del partido.
*   **Tipo de dato**: Estado transitorio. Al finalizar el torneo o el partido, el ganador puede guardarse en la fuente de verdad como histórico. El conteo granular es temporal.
*   **Estructura elegida**: `Sorted Set`. Garantiza que al momento de recibir múltiples votos atómicamente (`ZINCRBY`), la estructura mantiene su propio ordenamiento nativo `O(log N)`, ahorrando a la aplicación la tarea de ordenar en memoria los puntajes.

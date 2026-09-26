# Memoria y Escalabilidad

En un entorno en memoria, el recurso más crítico es la RAM. Redis no debe usarse para almacenar "todo lo posible de por vida". Este documento define cómo se comporta el servidor ante una situación límite y cómo puede evolucionar.

## Política de Memoria (maxmemory-policy)

Para el ambiente local del Hito 7, el módulo se configurará con un límite máximo (ej. `256mb` en scripts de inicialización).

*   **Política seleccionada**: `allkeys-lru`
    *   *Explicación*: Ante la presión de memoria (cuando la RAM de Redis está llena y debe insertar una clave nueva), esta política empieza a expulsar las claves menos utilizadas recientemente (*Least Recently Used*), sin importar si tienen o no un TTL asignado.
*   **Justificación de la elección**:
    *   **¿Por qué no `volatile-lru`?**: Si por algún error de código (bug) la aplicación escribe múltiples claves pesadas de caché pero *olvida* enviarles el TTL (`EX`), bajo `volatile-lru` Redis no las borraría y el servidor eventualmente rechazaría nuevas conexiones.
    *   **¿Por qué no `noeviction`?**: Si el servidor rechaza nuevas claves, toda la gente nueva que intente loguearse (nueva sesión) o ver un partido nuevo (nueva caché) recibiría errores. Preferimos botar una sesión antigua ociosa (forzando a un usuario inactivo a loguearse otra vez) a detener por completo el sistema entero.
*   **Efectos esperados**:
    *   *Sesiones*: Una sesión antigua sin actividad, pero que tal vez no había expirado, puede ser evicta temprano. La app solo verá un *Miss* y lo resolverá exigiendo login, por lo que es tolerante.
    *   *Caché*: Una caché poco consultada será borrada para dar lugar al partido en vivo. Tolera perfectamente este flujo por su diseño Cache-Aside.

## Persistencia vs Evicción
*   **TTL**: Decide cuándo un negocio *declara que un dato caducó*.
*   **Evicción (Memoria)**: Decide cuándo el *servidor está ahogado de recursos*.
*   **Persistencia (AOF/RDB)**: Asegura la recuperación en disco de claves *antes* de que venzan por TTL o caigan por evicción, ante casos donde se reinicie el contenedor. En el compose se fijó `--appendonly yes --save 60 1`.

## Pasos futuros para escalabilidad

El nodo único (Standalone) usado aquí está bien en el contexto de desarrollo y un tráfico acotado. En producción para el mundial, un solo servidor de Redis se quedaría rápidamente sin red y presentaría un Punto Único de Fallo.

1.  **Alta disponibilidad de Caché (Sentinel)**: Se replicarían los datos de caché de lectura a múltiples nodos "Replicas", mientras un "Primary" atiende invalidaciones. Sentinel proveería *failover* (redirigir si se cae el master).
2.  **Particionado Horizontal de Sesiones (Cluster)**: Como las sesiones no se deben mezclar con escrituras masivas, para soportar a millones de usuarios en paralelo se usaría Redis Cluster. La clave de sesión `sesion:{id_usuario}` usaría el hash tag automático para distribuirse de manera determinista (sharding) entre 10 o 20 nodos Master independientes, permitiendo escalar memoria disponible a Terabytes.

# Ciclo de Vida e Invalidación

El manejo del tiempo de vida (TTL) diferencia un simple almacén clave-valor de un módulo efectivo de sesiones y caché temporal. Este documento justifica y demuestra las decisiones tomadas para las sesiones y los datos de lectura rápida.

## 1. Ciclo de Vida de las Sesiones

### Lógica de Renovación
Una sesión no es indefinida, pero tampoco debe cerrarse si el usuario sigue usándola. Utiliza un modelo de inactividad de **30 minutos** (`1800 segundos`).

*   **Creación**: Se crea el Hash mediante `HSET` y se establece explícitamente su duración: `EXPIRE sesion:U019 1800`.
*   **Condición de Validez**: La aplicación solo confía en una petición si el `GET` (o `HGETALL`) de la clave de sesión retorna datos válidos y el TTL subyacente sigue activo.
*   **Renovación**: Solo se extiende la vida de una sesión si hay una acción genuina en la plataforma, actualizando el campo `ultimo_acceso` y renovando el límite máximo.
    ```redis
    HSET sesion:U019 ultimo_acceso "nuevo timestamp"
    EXPIRE sesion:U019 1800
    ```
*   **Comportamiento ante clave ausente**: Si la sesión no existe, o ya expiró en Redis (retorna `-2` al consultar `TTL`), la aplicación redirigirá al usuario a iniciar sesión de nuevo. Se aprovecha el mecanismo pasivo y activo de limpieza de Redis para la expiración.

---

## 2. Fuente de Verdad y Caché (Cache-Aside)

La caché **no es la fuente de verdad**. Si un nodo de Redis se pierde por completo (a pesar de la persistencia AOF configurada), la aplicación debe ser tolerante al fallo (capaz de reconstruir los datos).

### Patrón Utilizado (Cache-Aside / Lazy Loading)

1.  **Fuente de Verdad**: Los datos sobre la información de equipos y partidos residen originalmente en bases como MongoDB (Documental) y Neo4j (Grafos).
2.  **Condición de Cache Hit**: Si la clave `cache:partido:M001` existe en Redis y devuelve el valor (un JSON), la aplicación omite la consulta a bases pesadas, respondiendo en milisegundos.
3.  **Flujo ante un Cache Miss**: Si Redis retorna `(nil)` (la clave no existe):
    *   La API va a consultar MongoDB / Neo4j.
    *   Conforma el objeto JSON requerido.
    *   Inmediatamente lo escribe en Redis: `SET cache:partido:M001 "json_serializado" EX 60`.
    *   Y luego se lo retorna al cliente.
4.  **Estrategia de Coherencia e Invalidación**: Asumir que la caché es válida siempre, solo porque tiene un TTL (ej. `EX 60`), es peligroso. Si hay un *Gol*, no queremos que el usuario espere 60 segundos viendo el resultado anterior.
    *   *Invalidación de Negocio*: La API de carga de resultados en la fuente de verdad (ej. sumar un gol) realiza la actualización en la BD pesada e inmediatamente emite el comando `DEL cache:partido:M001` a Redis. El próximo lector provocará un Miss controlado, recargando el dato nuevo al instante.
    *   *TTL de seguridad*: El `EX 60` no es para refrescos normales. Sirve para mitigar si un *DEL* falla en la red: garantiza que, en el peor de los casos, la caché es eventualmente consistente a lo sumo en 1 minuto.

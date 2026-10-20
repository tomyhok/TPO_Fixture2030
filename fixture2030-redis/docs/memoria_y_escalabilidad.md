# Hito 7 — memoria y escalabilidad (corregido)

## Política elegida

El Compose raíz y el del módulo usan `--maxmemory 256mb --maxmemory-policy noeviction`.
Se conserva una sola instancia para el laboratorio. Las sesiones de autenticación y las copias
de caché tienen significados distintos aunque ambas puedan tener TTL:

| Dato | ¿Se puede reconstruir desde otra fuente? | Política de vigencia |
|---|---|---|
| Copia de ficha de equipo/partido | Sí, desde MongoDB/Neo4j | TTL y eliminación al actualizar el origen |
| Sesión autenticada | No equivale a una copia del perfil; contiene estado de acceso vigente | TTL de inactividad o invalidación explícita; no expulsión arbitraria |
| Encuesta abierta y contadores | Puede existir estado que no esté guardado en otra fuente | Conservar mientras sea necesario; definir conservación antes de borrar |

`volatile-lru` podía expulsar cualquier clave con TTL, incluida una sesión todavía activa.
El TTL expresa hasta cuándo debe ser válida una clave; no autoriza su descarte antes de ese
momento. Se corrige esa decisión: **noeviction preserva las claves existentes ante presión de
memoria y rechaza las escrituras que necesitan más memoria**. Se acepta que una nueva sesión,
una renovación o una carga de caché puedan fallar y deban comunicar ese error. No se promete
disponibilidad infinita ni protección frente a fallos del proceso o pérdida de persistencia.

Expiración y eliminación explícita siguen funcionando: una sesión puede vencer por inactividad
o cerrarse voluntariamente. Con noeviction, una copia de caché también ocupa memoria hasta
vencer o ser invalidada. El límite de 256 MB es de laboratorio, no capacidad suficiente para
millones de sesiones. Hay que medir tamaño de sesión y crecimiento antes de dimensionar.

## Verificación y operación

`CONFIG GET maxmemory-policy`, `INFO memory` e `INFO stats` permiten verificar política,
memoria usada, expiraciones, evicciones y rechazos. La revisión aplicó `CONFIG SET` sin reiniciar
la instancia para conservar sus claves; el Compose asegura la misma política al recrearla.
Se observó un TTL positivo en una clave temporal propia y se la eliminó al terminar.
[Evidencia](revision_2026-10-19/politica.json). No se llenó deliberadamente la instancia compartida:
no se presenta una prueba OOM que no fue ejecutada.

Monitorear memoria respecto del límite, errores de escritura y duración de sesiones. Ante
presión, reducir o invalidar copias reconstruibles mediante su ciclo de vida y aumentar capacidad
según mediciones. No acortar arbitrariamente la vigencia de autenticación para ocultar saturación.

## Persistencia y límites

Se conserva AOF y snapshot RDB en `~/docker/data/redis`. Las fichas siguen siendo copias;
las sesiones son estado de acceso temporal. La persistencia no reemplaza la política de vigencia
ni prueba alta disponibilidad. El único nodo local es un punto de fallo y comparte recursos con
los otros motores; no demuestra réplica, recuperación regional ni escala de producción.

Una separación futura en instancias distintas permitiría política de evicción de caché y política
de sesiones independientes. No se agrega ese despliegue para resolver el laboratorio: se usa
la política conservadora de una instancia y se explicita su costo de rechazar escrituras.

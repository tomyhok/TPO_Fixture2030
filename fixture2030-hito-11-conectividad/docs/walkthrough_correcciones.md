> Este walkthrough documenta la primera corrección del Hito 11, anterior a la devolución docente.
> Los conteos de pruebas y el diagnóstico del entorno que siguen son históricos. La revisión
> vigente está en `../../docs/walkthrough_correcciones_feedback.md`.

# Walkthrough de las correcciones del Hito 11

Revisión del 19/10/2026 sobre la rama `hito-11`. Los cambios están en el directorio
de trabajo: no se creó ningún commit, no se agregó nada al staging y no se hizo push.

## 1. Matriz: relacionar la API con cada dependencia

**Problema.** Las pruebas HTTP se guardan con `producto="api"`. La matriz calculaba
el estado únicamente con las filas cuyo producto era, por ejemplo, `mongodb`.
Por eso podía mostrar `disponible` y, al mismo tiempo, `API=FAIL`.

**Cambio.** En [`registro.py`](../scripts/conectividad/registro.py), la matriz
incorpora las pruebas HTTP que nombran a cada fuente en `datos.dependencias`.
Si la lectura nativa funciona y la API falla, la fuente queda `degradado`.
Una sonda negativa que falla también impide presentar el producto sin observaciones.

En [`api.py`](../scripts/conectividad/api.py) se identifican las fuentes afectadas
tanto en el diagnóstico como en `no_disponibles` de readiness. Si la API no es
alcanzable, esa falla se asocia a los productos evaluados. Las fuentes sanas no
heredan las advertencias de una dependencia ajena.

**Verificación.** Regresiones con una lectura nativa exitosa y HTTP 503, readiness
parcial y API inaccesible. Se comprueba el estado final de la matriz completa,
no solamente una función de clasificación aislada.

## 2. Modo estricto: registrar los errores del evaluador

**Problema.** Una variable como `REDIS_PORT=invalido` provocaba una excepción que
se imprimía, pero no entraba al conteo ni al JSON. `--estricto` terminaba con 0.

**Cambio.** [`evaluar_conectividad.py`](../scripts/evaluar_conectividad.py) registra
un `Resultado` FAIL de diagnóstico con hipótesis y siguiente paso. La fuente queda
`desconocido`, porque un error de configuración o del evaluador no demuestra que
el servidor esté caído. El modo estricto devuelve 1. Una capa desconocida, como
`lectrua`, se rechaza con código 2, en lugar de producir una evaluación vacía.

**Verificación.** Una prueba ejecuta el punto de entrada con un puerto inválido,
abre el JSON generado y verifica conteo, estado, explicación y código de salida.

## 3. Drivers oficiales y ejecución por capa

La Clase 12 propone probar cada producto con su cliente o driver. Se retiraron
los mensajes y parsers binarios escritos a mano:

- **Cassandra:** se eliminaron los frames OPTIONS/STARTUP y el lector que podía
  quedar en un bucle al recibir EOF antes del cuerpo. `cluster.connect()` negocia
  CQL; las operaciones de control usan el driver y timeouts explícitos.
- **Neo4j:** `driver.get_server_info()` reemplaza los bytes de negociación Bolt.
  Se mantienen `verify_authentication()`, las sesiones y las lecturas Cypher.
- **Redis:** `redis-py.ping()` reemplaza la serialización manual de RESP. Se utiliza
  un cliente sin credenciales para comprobar la respuesta básica y otro con la
  configuración de la API para identidad, permisos y lectura.

Cuando el driver negocia protocolo e identidad en una sola llamada, el resultado
lo explica. Las filas separadas no pretenden representar dos intercambios físicos
independientes. La prueba TCP sigue siendo independiente.

En [`cassandra.py`](../scripts/conectividad/productos/cassandra.py) se agregó una
inicialización de sesión reutilizable. `--capas contexto` y `--capas lectura`
abren la sesión necesaria aunque no se haya pedido la capa de autorización.
La lectura verifica el contexto antes de preparar su consulta. Ya no accede a
una variable `sesion` inexistente ni confunde metadata sin inicializar con una
base ausente.

También se corrigió la importación de `AuthenticationFailed`: pertenece a
`cassandra`, no a `cassandra.auth`. Los errores de identidad envueltos en
`NoHostAvailable` se reconocen sin perder la causa original.

**Verificación.** Pruebas de lectura y contexto aislados, clasificación de errores
de conexión/autenticación y una corrida contra los contenedores reales.

## 4. Sondas: comprobar el resultado y la causa

**Problema.** Algunas sondas devolvían OK al recibir cualquier respuesta. Por
ejemplo, un HTTP 200 con token inválido se describía como una identidad rechazada.
Con Cassandra sin keyspace se atribuía un `InvalidRequest` a una partición incompleta.

**Cambios.**

- **InfluxDB:** el token inválido debe recibir 401; la database inexistente debe
  recibir 404 con el motivo de contexto; una ventana vacía debe responder 200
  y devolver realmente `COUNT(*)=0`. Un 403 o 500 no prueba ausencia de datos.
- **Cassandra:** las sondas de tablas/particiones requieren contexto válido.
  Si falta, se omiten o quedan bloqueadas por la capa fallida. Se comprueba el
  recurso o motivo del `InvalidRequest`, en lugar de aceptar cualquier error.
  Se retiró la sonda de dirección privada que llamaba timeout a cualquier
  `NoHostAvailable`: ese error también puede envolver otras causas de conexión.
- **Neo4j:** la database inexistente debe producir `DatabaseNotFound`; un rechazo
  de credenciales no sirve como prueba de contexto. Las sondas verifican que el
  partido inexistente esté ausente y que el partido vacío tenga cero eventos.
- **MongoDB:** se comprueba la ausencia del documento, la colección y la database
  utilizadas como ejemplos negativos. Si existen, la sonda falla y lo explica.
- **Redis:** la expiración opcional debe observar una clave creada, TTL inicial
  positivo y ausencia con TTL -2 al finalizar.
- **IRIS:** se verifican `NO_ENCONTRADO`, `CLASS DOES NOT EXIST` y namespace
  inexistente, en vez de describir cualquier respuesta como éxito. La consulta
  diferencial de namespace también tiene límite de espera.

**Verificación.** Regresiones con respuestas correctas e incorrectas, errores de
otra causa y recursos de prueba que no cumplen la condición esperada.

## 5. Credenciales locales y documentación

Los tres Compose (raíz, MongoDB y Neo4j) leen las contraseñas de variables externas
obligatorias. [`.env.example`](../../.env.example) contiene nombres sin secretos;
el `.env` real queda excluido de Git. Se quitaron contraseñas literales y URI
autenticadas de los ejemplos de documentación.

Para este checkout se creó un `.env` raíz con las credenciales actuales de los
contenedores. No se imprimieron sus valores ni se cambiaron las contraseñas de
las bases. Los Compose independientes usan `--env-file ../.env`. La API conserva
su propio archivo `.env`: debe completarse con las mismas credenciales de las
fuentes y con el token/usuario que correspondan a InfluxDB e IRIS.

**Límite:** retirar las credenciales de los archivos actuales no las elimina del
historial previo. La rotación de esos valores sigue pendiente de coordinación;
no se reescribió el historial ni se alteraron usuarios existentes.

Se actualizaron README, capas, mapa, matriz, diagnóstico y limitaciones. La
evidencia del 17/10 se conserva identificada como histórica. No se reemplazaron
sus resultados por números que no se hayan medido.

## 6. Pruebas y resultados

Se retiró una prueba del parser CQL eliminado y se agregaron 22 casos de regresión.
También se aisló una prueba de configuración de la API: una contraseña heredada
del entorno ya no hace fallar una comprobación de contraseña vacía.

Desde la raíz, con Python 3.12 y los requisitos de la API instalados:

```powershell
python -m pytest fixture2030-hito-11-conectividad/tests -q
```

Resultado: **42 pruebas aprobadas**.

Desde `fixture2030-hito-10-api-integrada`:

```powershell
python -m pytest tests/unit -q
```

Resultado: **136 pruebas aprobadas**. Total: **178**.

Se validó la configuración de los tres Compose con `docker compose config --quiet`.
El archivo local `.env` queda ignorado y no hay contraseñas literales en los
Compose corregidos. `git diff --check` comprueba el formato del diff.

La [corrida nativa corregida](evidencia/revision_2026-10-19/README.md) dio
**43 OK, 1 WARN, 1 FAIL y 2 SKIP**. MongoDB, Neo4j y Redis pudieron leerse;
Cassandra informó correctamente el keyspace ausente. El modo estricto devolvió 1,
como corresponde a esa falla real de contexto, y no mostró sondas falsas en OK.

Esto no certifica una integración completa exitosa: el laboratorio todavía
necesita el keyspace de Cassandra, clases IRIS compatibles y el token de InfluxDB.
El token de InfluxDB se verificó el 23/10/2026: 14 OK y 0 FAIL
([salida](../../fixture2030-influxDB/docs/evidencia/09_conectividad.txt)).
No se cargaron ni borraron datos para ocultar esas condiciones.

## 7. Cómo revisar lo que quedó pendiente de guardar

```powershell
git status --short
git diff
```

Los archivos nuevos (pruebas, ejemplo de configuración, walkthrough y evidencia)
aparecen como no versionados hasta que se decida agregarlos. El `.env` con secretos
no debe aparecer en esa lista. El stash con las clases y las consignas se conserva.

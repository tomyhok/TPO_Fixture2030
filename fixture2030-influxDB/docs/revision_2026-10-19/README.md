# Reproducibilidad del entorno — Hito 8

Compose raíz y Compose del módulo declaran `influxdb:3-core`. Se corrigió el `latest` del
segundo. La etiqueta identifica la familia Core; puede cambiar con nuevas publicaciones.
Para identificar exactamente la ejecución aplicada, [compose_aplicado.json](compose_aplicado.json) conserva ID/digest de la imagen,
salida de `influxdb3 --version` y hashes de ambos Compose. El binario instalado es **3.12.0**.
Para repetir ese binario exacto se puede usar el digest registrado, conservando los demás parámetros.

El archivo verifica el entorno real, no repite la carga histórica de millones de puntos.
No está disponible el token del servidor actual. Las consultas de lectura devuelven 401 sin
credencial; la API informa `not_configured` y 503. Es necesario recuperar el token existente
para repetir validación, agregaciones y lectura integrada. No se inventó evidencia de consultas
ni se reinicializó el directorio para obtener una credencial nueva.

Las mediciones históricas se conservan con su versión declarada y no se atribuyen automáticamente
al Compose corregido. El script `scripts/verificar_entorno.py` permite registrar en una carpeta nueva
la imagen, versión y equivalencia de los parámetros del servicio de ambos Compose.

`entorno.json` y `primera_comprobacion_compose.json` conservan comprobaciones anteriores
de esta misma revisión. El registro vigente es `compose_aplicado.json`.

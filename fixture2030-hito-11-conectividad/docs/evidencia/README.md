# Evidencia del Hito 11

Generada con `bash scripts/generar_evidencia.sh` el 2026-10-17 entre las 00:32
y las 00:34 UTC, desde la notebook (Windows 11, Git Bash), con commit base
`db0f5fc` y los cambios del Hito 11. Toda la salida pasó por
`scripts/redactar.py`, que oculta contraseñas, tokens, URIs con credenciales y
la carpeta personal del usuario. `verificacion_secretos.txt` lo comprueba sobre
todos los archivos.

| Archivo | Qué demuestra | Requisitos |
|---|---|---|
| [`00_entorno_y_topologia.txt`](00_entorno_y_topologia.txt) | Versiones, contenedores, puertos publicados vs. internos, IP de la red Compose, volúmenes | RF2, RNF18 |
| [`resultados_tcp.txt`](resultados_tcp.txt) / `.json` | Configuración (secretos ocultos y origen de cada valor), resolución, TCP y estado del contenedor; los seis quedan "desconocido" | RF3, RF4, RF5 |
| [`resultados_clientes.txt`](resultados_clientes.txt) / `.json` | Las 8 capas por producto con su driver + sondas (incluida la expiración en Redis) | RF6–RF14, RNF2, RNF4 |
| [`resultados_clientes_contenedor.txt`](resultados_clientes_contenedor.txt) | CLI oficiales dentro de cada contenedor (otro origen) | RF6, RNF4 |
| [`resultados_red_docker.txt`](resultados_red_docker.txt) | El mismo diagnóstico desde la red de Compose (nombres de servicio) y el error de usar `127.0.0.1` dentro de un contenedor | RNF3, restricción "Red" |
| [`resultados_api.txt`](resultados_api.txt) / `.json` | 19 rutas GET con request ID, status, tiempo, clase de resultado y líneas de log | RF15, RF18, RF19, 5.5 |
| [`resultados_completo.txt`](resultados_completo.txt) / `.json`, [`matriz_completa.md`](matriz_completa.md) | Modo completo y matriz de conectividad | RF16, RNF9, RNF18 |
| [`fallo_controlado_mongodb.txt`](fallo_controlado_mongodb.txt) | MongoDB detenido → diagnóstico, respuestas y log de la API → recuperación → datos y volumen conservados | RF20, RF21, 5.7 |
| [`escenarios_configuracion.txt`](escenarios_configuracion.txt) | Host, puerto, contexto, credencial y timeout incorrectos con su corrección; API temporal mal configurada (503/504 identificando la fuente) | RF17, RF18, RF20, 5.7 |
| [`logs_api_h11.txt`](logs_api_h11.txt) | Líneas del log de la API con request ID `h11-*`: ruta, dependencia, operación, resultado y duración | RF19, RNF11 |
| [`verificacion_secretos.txt`](verificacion_secretos.txt) | Búsqueda de cada valor secreto configurado en toda la evidencia (sin mostrarlo) | RNF7, RNF8 |
| [`capturas_redactadas/`](capturas_redactadas/README.md) | Política de capturas | RNF8 |

Los `.json` tienen, por prueba: instante UTC, producto, capa, prueba, estado,
duración, destino, detalle, hipótesis y siguiente paso. Tienen además los
metadatos de la corrida (commit, origen, versiones de los drivers, timeouts y
archivos de configuración usados).

# Contratos y errores

El contrato ejecutable está en [OpenAPI](../openapi/openapi.yaml); se genera desde las seis rutas,
schemas de respuesta y validaciones. No describe rutas eliminadas. Las respuestas son JSON.
Los valores del usuario son parámetros, nunca fragmentos de SQL, CQL o Cypher.

| Situación | HTTP | Tratamiento |
|---|---|---|
| Lectura correcta o colección vacía | 200 | Modelo de la ruta; listas vacías permitidas |
| Formato, rango o intervalo inválido | 400 | `VALIDACION`; sin acceder a fuentes |
| Objeto ausente | 404 | `RECURSO_NO_ENCONTRADO` o `SESION_NO_VIGENTE` |
| Método no implementado | 405 | `METODO_NO_PERMITIDO` |
| Falla inesperada de la aplicación | 500 | `ERROR_INTERNO`; detalle solo en log |
| Fuente inaccesible o sin configuración necesaria | 503 | `DEPENDENCIA_NO_DISPONIBLE` |
| Fuente excede límite de espera | 504 | `DEPENDENCIA_TIMEOUT` |

Los errores tienen `error.codigo`, `error.mensaje`, `error.detalles` y un identificador de solicitud.
`X-Request-ID` aparece también en los logs. Las consultas de estadísticas exigen zona horaria,
inicio anterior al fin y duración de hasta tres horas. Los comentarios requieren una fecha real
AAAAMMDDHHMM y un cursor UUID v1 si se suministra. Los límites acotan la cantidad devuelta.

Se eliminaron los contratos de altas, transiciones, invalidación y publicación: la integración
se demuestra mediante lecturas, sin sumar reglas de negocio de otros hitos.

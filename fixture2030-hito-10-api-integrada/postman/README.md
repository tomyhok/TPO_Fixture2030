# Postman — alcance esencial

Importar `fixture2030_collection.json` y el entorno local o de contenedor.
La variable `base_url` apunta a la API. Diez GET: seis lecturas representativas, un objeto ausente,
una entrada inválida, una lista vacía y salud. No se escriben datos ni se usan claves de idempotencia.
La sesión puede estar vencida (404 válido). InfluxDB necesita el token configurado en la API.
La colección no es evidencia de ejecución hasta correrla y guardar sus resultados.

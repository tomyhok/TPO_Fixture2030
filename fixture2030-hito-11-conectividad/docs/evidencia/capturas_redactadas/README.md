# Capturas redactadas

La evidencia de este hito es **texto reproducible** (salidas de los scripts,
JSON y líneas de log), generado por `scripts/generar_evidencia.sh` y filtrado
por `scripts/redactar.py`. Se eligió texto y no capturas de pantalla porque se
puede regenerar, comparar con `git diff` y verificar automáticamente
(`verificacion_secretos.txt`), cosa que con una imagen no se puede hacer.

Si se agregan capturas (por ejemplo del Browser de Neo4j o del Management
Portal de IRIS), antes de versionarlas hay que:

* ocultar barras de URL con credenciales, campos de contraseña, tokens y la carpeta personal del usuario;
* recortar cualquier dato personal;
* nombrarlas con fecha y producto (`2026-10-17_neo4j_browser.png`).

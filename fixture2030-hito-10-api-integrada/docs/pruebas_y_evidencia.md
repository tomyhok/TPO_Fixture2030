# Pruebas y evidencia

La revisión concentra la verificación del Hito 10 en seis lecturas, sus contratos, validación,
ausencia y errores de dependencia. Se preservan las regresiones de salud requeridas por el Hito 11.

Comandos desde el módulo:

```sh
python -m pytest tests/unit -q
python -m pytest tests/integration/test_dependencias_caidas.py -q
python -m pytest tests/integration/test_api_integracion.py -q
python scripts/exportar_openapi.py
python scripts/generar_evidencia.py
```

La tercera orden necesita seis fuentes preparadas y puede saltearse si falta alguna; un skip
no demuestra funcionamiento. La última captura GET por HTTP contra la API iniciada y escribe
en una carpeta nueva, sin reemplazar evidencia histórica. Postman tiene 10 solicitudes esenciales.

Resultados de esta revisión: [evidencia vigente](evidencia/revision_2026-10-19/README.md).
Las pruebas con dobles no prueban conectividad; las pruebas de puertos cerrados no prueban carga;
las lecturas reales registradas mediante TestClient prueban rutas y clientes, pero no el listener HTTP.
No se usan estos resultados para garantizar los objetivos de latencia o escala del escenario.

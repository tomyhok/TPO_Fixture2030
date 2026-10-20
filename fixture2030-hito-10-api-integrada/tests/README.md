# Pruebas

Desde el módulo y con Python 3.12/dependencias instaladas:
`python -m pytest tests/unit -q` y
`python -m pytest tests/integration/test_dependencias_caidas.py -q`.

Las unitarias cubren seis lecturas, validaciones, errores, contrato y salud del Hito 11.
Las de fallas usan los drivers reales contra puertos locales cerrados o un listener que no responde.
`tests/integration/test_api_integracion.py` necesita las seis fuentes disponibles y muestras cargadas.
No reinicia actas, publica comentarios ni modifica sesiones. Un salto por configuración faltante
debe informarse separado de los casos aprobados.

# API REST integrada - Hito 10 (modo contenedor, opcional)
# Se construye y levanta junto con las bases con docker-compose.api.yml.
FROM python:3.12-slim

WORKDIR /api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# cassandra-driver en versión Python pura: evita compilar extensiones C/Cython
# (minutos de build) y alcanza para el volumen de la API.
ENV CASS_DRIVER_NO_CYTHON=1 CASS_DRIVER_NO_EXTENSIONS=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Usuario sin privilegios; la configuración llega por variables de entorno.
RUN useradd --create-home --uid 10001 api
USER api

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

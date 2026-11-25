# Dockerfile - Imagen de la API de ORIZEN
# Sirve igual para local (docker compose) y para Render.
FROM python:3.12-slim

# Python sin archivos .pyc y con los logs al instante
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias: si no cambian, Docker reutiliza esta capa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después el código
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

# Usuario sin privilegios (no correr como root)
RUN useradd --create-home orizen
USER orizen

EXPOSE 8000

# Aplica las migraciones y arranca la API.
# Render pasa el puerto en $PORT; en local se usa 8000.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

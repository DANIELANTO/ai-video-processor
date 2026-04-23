FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para compilar ciertos paquetes y FFmpeg
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copiar e instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY ./app ./app

# Exponer el puerto
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "app.presentation.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
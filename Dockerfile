FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema si son necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . /app

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV IPFS_API_URL=/ip4/127.0.0.1/tcp/5001

# El comando se especificará en docker-compose
CMD ["python", "menu.py"]
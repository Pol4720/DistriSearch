FROM python:3.11-slim

WORKDIR /app

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente modular
COPY core/ ./core/
COPY node/ ./node/
COPY storage/ ./storage/
COPY network/ ./network/
COPY consensus/ ./consensus/
COPY replication/ ./replication/
COPY balancer/ ./balancer/
COPY sharding/ ./sharding/

# Copiar archivos raíz necesarios
COPY config.py .
COPY utils.py .
COPY docker-entrypoint.py .

# Crear directorio para datos
RUN mkdir -p /app/data

# Variables de entorno por defecto
ENV NODE_ID=0
ENV DIMENSIONS=20
ENV HOST=0.0.0.0
ENV PORT=8000

# Script de entrada
COPY docker-entrypoint.py .

EXPOSE 8000

CMD ["python", "docker-entrypoint.py"]

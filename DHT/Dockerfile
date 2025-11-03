# Dockerfile para el servicio DHT (Distributed Hash Table)
FROM python:3.10-slim

LABEL maintainer="DistriSearch Team"
LABEL description="DHT (Chord) service for distributed file search"

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Exponer puertos
# 8080: API HTTP (Flask)
# 2000: Socket P2P (Chord)
EXPOSE 8080 2000

# Variables de entorno por defecto
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PORT=2000
ENV MAX_BITS=10

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/server/rest/DHT/imprimirSucPred', timeout=5)" || exit 1

# Comando de inicio
CMD ["python", "main.py"]

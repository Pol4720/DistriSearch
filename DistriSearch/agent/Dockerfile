FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
RUN pip install --no-cache-dir requests aiohttp pyyaml

# Copiar archivos del agente
COPY *.py ./
COPY config.yaml ./

# Crear carpeta compartida
RUN mkdir -p /app/shared

# Volumen para montar la carpeta compartida del host
VOLUME ["/app/shared"]

# Puerto para el servidor de archivos
EXPOSE 8081

# Ejecutar el agente
CMD ["python", "agent.py"]

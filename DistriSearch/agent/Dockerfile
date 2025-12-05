FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas para pandas y openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	libxml2-dev \
	libxslt1-dev \
	libjpeg62-turbo-dev \
	libpng-dev \
	&& rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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

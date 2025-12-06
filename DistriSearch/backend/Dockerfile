FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

# Crear carpetas comunes de datos en la imagen
RUN mkdir -p /app/data /app/central_shared /app/uploads

WORKDIR /app/backend

# Exponer puertos
EXPOSE 8000
EXPOSE 5000/udp
EXPOSE 5001/udp

# Comando para ejecutar la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

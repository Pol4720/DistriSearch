FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

# Crear carpetas comunes de datos en la imagen (pueden ser montadas en runtime)
RUN mkdir -p /app/data /app/central_shared

WORKDIR /app/backend

# Exponer el puerto para la API
EXPOSE 8000

# Comando para ejecutar la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

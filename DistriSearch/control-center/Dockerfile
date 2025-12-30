FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for both backend and frontend
COPY backend/requirements.txt backend-requirements.txt
COPY frontend/requirements.txt frontend-requirements.txt

RUN pip install --no-cache-dir -r backend-requirements.txt && \
    pip install --no-cache-dir -r frontend-requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Copy streamlit config
COPY frontend/.streamlit /app/frontend/.streamlit

# Create startup script
RUN echo '#!/bin/bash\n\
echo "🚀 Iniciando Control Center..."\n\
cd /app/backend && python main.py &\n\
sleep 2\n\
cd /app/frontend && streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true\n\
' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8888 8501

CMD ["/bin/bash", "/app/start.sh"]

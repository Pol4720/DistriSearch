# DistriSearch Master Node Dockerfile
# Raft Consensus Leader + Cluster Coordinator

FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY master/requirements.txt ./requirements-master.txt
COPY backend/requirements.txt ./requirements-backend.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-backend.txt && \
    pip install --no-cache-dir -r requirements-master.txt

# Copy source code
COPY backend/ ./backend/
COPY master/ ./master/
COPY shared/ ./shared/

# Copy entrypoint script
COPY docker/master/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ROLE=master \
    API_HOST=0.0.0.0 \
    API_PORT=8001

# Expose Master API port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "master.app.main:app", "--host", "0.0.0.0", "--port", "8001"]

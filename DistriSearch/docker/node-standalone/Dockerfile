# ============================================================================
# DistriSearch Node STANDALONE - All-in-One Container
# ============================================================================
# Este Dockerfile crea un contenedor COMPLETAMENTE AUTÓNOMO con:
# - MongoDB (base de datos local)
# - Redis (cache local)
# - Backend (FastAPI)
# - Frontend (Nginx)
#
# ARQUITECTURA:
# - Usa docker run (NO docker service) para mantener independencia
# - La red overlay de Swarm se usa SOLO para comunicación entre nodos
# - Cada nodo es completamente autónomo y sobrevive particiones de red
# - El algoritmo BULLY maneja la elección de líder a nivel de aplicación
#
# OPTIMIZACIÓN:
# - MongoDB y Redis se copian desde imágenes locales (no descarga)
# - Usa multi-stage build para minimizar tamaño final
# ============================================================================

# ============================================================================
# Stage 0: Extract MongoDB binaries from official image
# ============================================================================
FROM mongo:4.4 AS mongodb-source

# ============================================================================
# Stage 0b: Extract Redis binaries from official image
# ============================================================================
FROM redis:7-alpine AS redis-source

# ============================================================================
# Stage 1: Build Frontend
# ============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production=false 2>/dev/null || npm install

# Copy frontend source
COPY frontend/ ./

# Build the React application
RUN npm run build

# ============================================================================
# Stage 2: Build Backend Dependencies
# ============================================================================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY backend/requirements.txt ./
ENV PIP_DEFAULT_TIMEOUT=120
RUN pip install --no-cache-dir -r requirements.txt --timeout 120

# ============================================================================
# Stage 3: Final Runtime Image (ALL-IN-ONE)
# ============================================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="DistriSearch Team"
LABEL description="DistriSearch Standalone Node - MongoDB + Redis + Backend + Frontend"
LABEL version="2.0-standalone-optimized"

# Install runtime dependencies (NO MongoDB, NO Redis - se copian desde stages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    openssl \
    procps \
    net-tools \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Copy MongoDB binaries from official image (FAST - no download)
# ============================================================================
COPY --from=mongodb-source /usr/bin/mongod /usr/bin/mongod
COPY --from=mongodb-source /usr/bin/mongo /usr/bin/mongo
COPY --from=mongodb-source /usr/bin/mongos /usr/bin/mongos

# Create MongoDB user and directories
RUN groupadd -r mongodb && useradd -r -g mongodb mongodb \
    && mkdir -p /data/db /var/log/mongodb \
    && chown -R mongodb:mongodb /data/db /var/log/mongodb

# ============================================================================
# Copy Redis binaries from official image (FAST - no download)
# ============================================================================
COPY --from=redis-source /usr/local/bin/redis-server /usr/bin/redis-server
COPY --from=redis-source /usr/local/bin/redis-cli /usr/bin/redis-cli

# Create Redis user and directories
RUN groupadd -r redis && useradd -r -g redis redis \
    && mkdir -p /var/lib/redis /var/log/redis /etc/redis \
    && chown -R redis:redis /var/lib/redis /var/log/redis

WORKDIR /app

# Copy virtual environment from builder
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend from builder
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# Copy backend source code
COPY backend/ ./backend/
COPY shared/ ./shared/

# Copy nginx configuration for frontend
COPY docker/node-standalone/nginx.conf /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy SSL generation script
COPY docker/node-standalone/generate-ssl.sh /generate-ssl.sh
RUN chmod +x /generate-ssl.sh

# Copy supervisor configuration (manages ALL services)
COPY docker/node-standalone/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy entrypoint script
COPY docker/node-standalone/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /data/uploads /var/log/distrisearch /var/run/supervisor

# ============================================================================
# Environment Variables (defaults, override with docker run -e)
# ============================================================================
ENV NODE_ID=node-1
ENV NODE_ROLE=peer
ENV API_PORT=8000
ENV MONGODB_DATABASE=distrisearch
ENV JWT_SECRET=distrisearch-shared-secret-2026
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ============================================================================
# Ports
# ============================================================================
# 80   - HTTP (Frontend via Nginx)
# 443  - HTTPS (Frontend via Nginx)
# 8000 - API (Backend FastAPI)
# 27017 - MongoDB (internal, not exposed by default)
# 6379  - Redis (internal, not exposed by default)
EXPOSE 80 443 8000

# ============================================================================
# Volumes (for data persistence)
# ============================================================================
VOLUME ["/data/db", "/data/uploads", "/var/lib/redis"]

# ============================================================================
# Health Check
# ============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/api/v1/health/live || exit 1

# ============================================================================
# Entrypoint
# ============================================================================
ENTRYPOINT ["/entrypoint.sh"]

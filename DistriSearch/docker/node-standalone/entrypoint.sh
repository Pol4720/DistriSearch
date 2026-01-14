#!/bin/bash
# ============================================================================
# DistriSearch Standalone Node - Entrypoint
# ============================================================================
# Este script inicializa TODOS los servicios dentro del contenedor:
# 1. MongoDB (base de datos local)
# 2. Redis (cache local)
# 3. Backend (FastAPI)
# 4. Frontend (Nginx)
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch Standalone Node"
echo "  Node ID: ${NODE_ID:-node-1}"
echo "=============================================="

# ============================================================================
# 1. Setup SSL Certificates
# ============================================================================
echo "[1/5] Generando certificados SSL..."
if [ ! -f /etc/nginx/ssl/server.crt ]; then
    /generate-ssl.sh
fi

# ============================================================================
# 2. Configure MongoDB
# ============================================================================
echo "[2/5] Configurando MongoDB..."

# Create MongoDB config (compatible con MongoDB 7.0+)
cat > /etc/mongod.conf << EOF
storage:
  dbPath: /data/db

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 127.0.0.1
EOF

# Ensure MongoDB directories exist and have correct permissions
mkdir -p /data/db /var/log/mongodb
chown -R mongodb:mongodb /data/db /var/log/mongodb 2>/dev/null || true

# ============================================================================
# 3. Configure Redis
# ============================================================================
echo "[3/5] Configurando Redis..."

# Create Redis config
cat > /etc/redis/redis.conf << EOF
bind 127.0.0.1
port 6379
daemonize no
dir /var/lib/redis
logfile /var/log/redis/redis.log
loglevel notice
save 900 1
save 300 10
save 60 10000
EOF

# Ensure Redis directories exist
mkdir -p /var/lib/redis /var/log/redis
chown -R redis:redis /var/lib/redis /var/log/redis 2>/dev/null || true

# ============================================================================
# 4. Configure Backend Environment
# ============================================================================
echo "[4/5] Configurando Backend..."

# Set environment variables for backend
export NODE_ID="${NODE_ID:-node-1}"
export NODE_ROLE="${NODE_ROLE:-peer}"
export API_PORT="${API_PORT:-8000}"

# MongoDB connection (LOCAL - dentro del mismo contenedor)
export MONGODB_URI="mongodb://127.0.0.1:27017/${MONGODB_DATABASE:-distrisearch}"
export LOCAL_MONGODB_URI="mongodb://127.0.0.1:27017"
export MONGODB_DATABASE="${MONGODB_DATABASE:-distrisearch}"

# Redis connection (LOCAL - dentro del mismo contenedor)
export REDIS_URL="redis://127.0.0.1:6379"
export LOCAL_REDIS_URL="redis://127.0.0.1:6379"
export COORDINATOR_REDIS_URL="redis://127.0.0.1:6379"

# Cluster configuration
export CLUSTER_ID="${CLUSTER_ID:-distrisearch-cluster}"
export JWT_SECRET="${JWT_SECRET:-distrisearch-shared-secret-2026}"

# BULLY algorithm for leader election
export BULLY_ENABLED="${BULLY_ENABLED:-true}"
export BULLY_PEERS="${BULLY_PEERS:-}"

# Node address (para comunicación con otros nodos)
# Esto debe ser la IP o hostname accesible desde otras máquinas
export NODE_ADDRESS="${NODE_ADDRESS:-$(hostname -I | awk '{print $1}')}"

echo "   NODE_ID: $NODE_ID"
echo "   NODE_ADDRESS: $NODE_ADDRESS"
echo "   MONGODB_URI: $MONGODB_URI"
echo "   REDIS_URL: $REDIS_URL"
echo "   BULLY_PEERS: $BULLY_PEERS"

# ============================================================================
# 5. Create uploads directory
# ============================================================================
echo "[5/5] Preparando directorios..."
mkdir -p /data/uploads
chmod 755 /data/uploads

# ============================================================================
# Start all services with Supervisor
# ============================================================================
echo ""
echo "=============================================="
echo "  Iniciando servicios con Supervisor..."
echo "=============================================="

exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf

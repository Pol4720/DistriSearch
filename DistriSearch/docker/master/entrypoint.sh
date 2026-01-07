#!/bin/bash
set -e

echo "=== DistriSearch Master Node Starting ==="
echo "NODE_ID: ${NODE_ID:-auto}"
echo "NODE_ROLE: ${NODE_ROLE:-master}"

# Generate NODE_ID if not provided
if [ -z "$NODE_ID" ]; then
    export NODE_ID="master-$(hostname | cut -c1-8)"
    echo "Generated NODE_ID: $NODE_ID"
fi

# ============================================================================
# NOTA: El Master NO usa MongoDB (arquitectura AP)
# - SQLite (Raft-replicado): metadatos del cluster
# - Redis: cache de sesiones y coordinación
# - Los documentos se almacenan SOLO en los Slaves
# ============================================================================

# Wait for Redis to be ready (REQUIRED for Master)
echo "Waiting for Redis..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "import redis; redis.Redis.from_url('${REDIS_URL}').ping()" 2>/dev/null; then
        echo "Redis is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for Redis... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "WARNING: Redis not available, continuing anyway..."
fi

# Create necessary directories
mkdir -p /app/data/raft /app/data/vptree /app/logs

echo "Starting Master node..."
exec "$@"

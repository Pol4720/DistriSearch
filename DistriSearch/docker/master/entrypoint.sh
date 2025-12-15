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

# Wait for MongoDB to be ready
echo "Waiting for MongoDB..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "from pymongo import MongoClient; MongoClient('${MONGODB_URI}', serverSelectionTimeoutMS=2000).admin.command('ping')" 2>/dev/null; then
        echo "MongoDB is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for MongoDB... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Could not connect to MongoDB!"
    exit 1
fi

# Wait for Redis to be ready (optional)
echo "Checking Redis availability..."
for i in $(seq 1 10); do
    if python -c "import redis; redis.Redis.from_url('${REDIS_URL}').ping()" 2>/dev/null; then
        echo "Redis is ready!"
        break
    fi
    echo "Waiting for Redis... ($i/10)"
    sleep 1
done

# Create necessary directories
mkdir -p /app/data/raft /app/data/vptree /app/logs

echo "Starting Master node..."
exec "$@"

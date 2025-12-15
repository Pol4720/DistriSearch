#!/bin/bash
set -e

echo "=== DistriSearch Slave Node Starting ==="
echo "NODE_ID: ${NODE_ID:-auto}"
echo "NODE_ROLE: ${NODE_ROLE:-slave}"
echo "MASTER_HOST: ${MASTER_HOST:-master}"
echo "HTTPS_ENABLED: ${HTTPS_ENABLED:-true}"

# Generate NODE_ID if not provided
if [ -z "$NODE_ID" ]; then
    export NODE_ID="slave-$(hostname | cut -c1-8)"
    echo "Generated NODE_ID: $NODE_ID"
fi

# Generate SSL certificates if HTTPS is enabled
if [ "${HTTPS_ENABLED:-true}" = "true" ]; then
    echo "Generating SSL certificates..."
    mkdir -p /etc/nginx/ssl
    
    # Only generate if certificates don't exist
    if [ ! -f /etc/nginx/ssl/server.crt ] || [ ! -f /etc/nginx/ssl/server.key ]; then
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout /etc/nginx/ssl/server.key \
            -out /etc/nginx/ssl/server.crt \
            -subj "/C=ES/ST=Madrid/L=Madrid/O=DistriSearch/OU=Development/CN=localhost" \
            -addext "subjectAltName=DNS:localhost,DNS:distrisearch.local,IP:127.0.0.1" 2>/dev/null || \
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout /etc/nginx/ssl/server.key \
            -out /etc/nginx/ssl/server.crt \
            -subj "/C=ES/ST=Madrid/L=Madrid/O=DistriSearch/OU=Development/CN=localhost"
        
        chmod 600 /etc/nginx/ssl/server.key
        chmod 644 /etc/nginx/ssl/server.crt
        echo "SSL certificates generated successfully!"
    else
        echo "SSL certificates already exist."
    fi
    
    # Use HTTPS nginx configuration
    cp /etc/nginx/sites-available/https /etc/nginx/sites-available/default
    echo "HTTPS configuration enabled."
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
    echo "WARNING: Could not connect to MongoDB, starting anyway..."
fi

# Wait for Master to be ready (optional, slave can start without master)
echo "Checking Master availability..."
MASTER_READY=false
for i in $(seq 1 10); do
    if curl -sf "http://${MASTER_HOST}:${MASTER_PORT:-8001}/health" >/dev/null 2>&1; then
        echo "Master is ready!"
        MASTER_READY=true
        break
    fi
    echo "Waiting for Master... ($i/10)"
    sleep 2
done

if [ "$MASTER_READY" = false ]; then
    echo "WARNING: Master not available, slave will retry connection..."
fi

# Create necessary directories
mkdir -p /app/data/documents /app/data/index /app/logs

# Set proper permissions
chown -R www-data:www-data /var/www/html

echo "Starting services via supervisord..."
exec "$@"

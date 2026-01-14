#!/bin/bash
# Generate self-signed SSL certificates for HTTPS
# These are for development/testing only

SSL_DIR="/etc/nginx/ssl"
mkdir -p "$SSL_DIR"

if [ ! -f "$SSL_DIR/server.crt" ] || [ ! -f "$SSL_DIR/server.key" ]; then
    echo "Generating self-signed SSL certificate..."
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/server.key" \
        -out "$SSL_DIR/server.crt" \
        -subj "/C=US/ST=State/L=City/O=DistriSearch/OU=Development/CN=localhost" \
        2>/dev/null
    
    chmod 600 "$SSL_DIR/server.key"
    chmod 644 "$SSL_DIR/server.crt"
    
    echo "SSL certificate generated successfully"
else
    echo "SSL certificate already exists"
fi

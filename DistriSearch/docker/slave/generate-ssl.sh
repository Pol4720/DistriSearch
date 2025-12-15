#!/bin/bash
# Generate self-signed SSL certificates for DistriSearch
# For production, use Let's Encrypt or a proper CA

CERT_DIR="/etc/nginx/ssl"
DOMAIN="distrisearch.local"

# Create directory
mkdir -p $CERT_DIR

# Generate private key and certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $CERT_DIR/server.key \
    -out $CERT_DIR/server.crt \
    -subj "/C=ES/ST=Madrid/L=Madrid/O=DistriSearch/OU=Development/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"

# Set permissions
chmod 600 $CERT_DIR/server.key
chmod 644 $CERT_DIR/server.crt

echo "SSL certificates generated successfully in $CERT_DIR"

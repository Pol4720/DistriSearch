#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Script para actualizar upstreams de Nginx dinámicamente
# Consulta al Master para obtener lista de slaves activos
# ═══════════════════════════════════════════════════════════════════════════

set -e

UPSTREAM_DIR="/etc/nginx/conf.d/upstreams"
MASTER_HOST="${MASTER_HOST:-master}"
MASTER_PORT="${MASTER_PORT:-8001}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-30}"

mkdir -p "$UPSTREAM_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

generate_upstreams() {
    log "Fetching active nodes from master..."
    
    # Intentar obtener nodos del master - primero el cluster status, luego nodes
    NODES_JSON=$(curl -sf "http://${MASTER_HOST}:${MASTER_PORT}/api/v1/cluster/nodes" 2>/dev/null || \
                 curl -sf "http://${MASTER_HOST}:${MASTER_PORT}/api/v1/cluster/status" 2>/dev/null || echo "")
    
    if [ -z "$NODES_JSON" ] || [ "$NODES_JSON" = "null" ] || [ "$NODES_JSON" = "[]" ]; then
        log "WARNING: Could not fetch nodes from master, using fallback"
        # Fallback: buscar slaves por DNS de Docker
        cat > "${UPSTREAM_DIR}/slaves.conf" << EOF
# Fallback configuration - discovering via Docker DNS
upstream slave_api {
    server ${MASTER_HOST}:${MASTER_PORT};
    keepalive 16;
}

upstream slave_frontend {
    server ${MASTER_HOST}:${MASTER_PORT};
    keepalive 8;
}
EOF
        return 1
    fi
    
    # Parsear JSON y generar configuración
    # Extraer slaves activos (status=healthy, role=slave)
    SLAVE_SERVERS=$(echo "$NODES_JSON" | python3 -c "
import sys
import json
import os

master_host = os.environ.get('MASTER_HOST', 'master')
master_port = os.environ.get('MASTER_PORT', '8001')

try:
    data = json.load(sys.stdin)
    
    # Handle both list response and object with nodes key
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict):
        nodes = data.get('nodes', [])
    else:
        nodes = []
    
    api_servers = []
    frontend_servers = []
    
    for node in nodes:
        role = node.get('role', '')
        status = node.get('status', '')
        
        # Aceptar slaves que estén healthy o unknown (recién registrados)
        if role == 'slave' and status in ['healthy', 'unknown', 'active']:
            address = node.get('address', '')
            node_id = node.get('node_id', '')
            port = node.get('port', 8000)
            
            # Usar node_id como hostname si address está vacío
            host = address if address else node_id
            if not host:
                continue
                
            # Extraer solo el host si viene con puerto
            if ':' in host:
                host = host.split(':')[0]
            
            # Para API (puerto 8000)
            api_servers.append(f'    server {host}:{port} max_fails=3 fail_timeout=30s;')
            # Para Frontend (puerto 80)
            frontend_servers.append(f'    server {host}:80 max_fails=3 fail_timeout=30s;')
    
    if api_servers:
        print('# Generated upstream configuration')
        print(f'# Found {len(api_servers)} healthy slave(s)')
        print('')
        print('upstream slave_api {')
        print('    least_conn;')
        for s in api_servers:
            print(s)
        print('    keepalive 32;')
        print('}')
        print('')
        print('upstream slave_frontend {')
        print('    least_conn;')
        for s in frontend_servers:
            print(s)
        print('    keepalive 16;')
        print('}')
    else:
        print('# No healthy slaves found - using master as fallback')
        print('upstream slave_api {')
        print(f'    server {master_host}:{master_port};')
        print('    keepalive 16;')
        print('}')
        print('upstream slave_frontend {')
        print(f'    server {master_host}:{master_port};')
        print('    keepalive 8;')
        print('}')
        
except Exception as e:
    print(f'# Error parsing nodes: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$SLAVE_SERVERS" ]; then
        echo "$SLAVE_SERVERS" > "${UPSTREAM_DIR}/slaves.conf"
        log "Updated upstreams configuration"
        return 0
    else
        log "WARNING: Failed to generate upstream config"
        return 1
    fi
}

reload_nginx() {
    if nginx -t 2>/dev/null; then
        nginx -s reload 2>/dev/null || true
        log "Nginx configuration reloaded"
    else
        log "ERROR: Nginx configuration test failed"
    fi
}

# Generar configuración inicial vacía
cat > "${UPSTREAM_DIR}/slaves.conf" << 'EOF'
# Initial configuration - waiting for slaves to register
upstream slave_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

upstream slave_frontend {
    server 127.0.0.1:80;
    keepalive 8;
}
EOF

log "Starting upstream update daemon (interval: ${UPDATE_INTERVAL}s)"

# Loop principal
while true; do
    if generate_upstreams; then
        reload_nginx
    fi
    sleep "$UPDATE_INTERVAL"
done

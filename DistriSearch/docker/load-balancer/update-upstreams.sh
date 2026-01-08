#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Script para actualizar upstreams de Nginx dinámicamente
# Compatible con arquitectura HA donde el líder es elegido por Raft
# ═══════════════════════════════════════════════════════════════════════════

set -e

UPSTREAM_DIR="/etc/nginx/conf.d/upstreams"
# Para HA, usamos el servicio de nodos (tasks.node) en vez de un master fijo
NODE_SERVICE="${NODE_SERVICE:-tasks.node}"
NODE_PORT="${NODE_PORT:-8000}"
# Fallback al master fijo (compatibilidad hacia atrás)
MASTER_HOST="${MASTER_HOST:-master}"
MASTER_PORT="${MASTER_PORT:-8001}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-30}"
# Modo HA: descubre nodos dinámicamente
HA_MODE="${HA_MODE:-false}"

mkdir -p "$UPSTREAM_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Descubrir el líder actual consultando cualquier nodo
discover_leader() {
    local nodes=("$@")
    for node in "${nodes[@]}"; do
        LEADER_INFO=$(curl -sf "http://${node}:${NODE_PORT}/api/v1/cluster/master" 2>/dev/null || echo "")
        if [ -n "$LEADER_INFO" ] && [ "$LEADER_INFO" != "null" ]; then
            LEADER_ADDRESS=$(echo "$LEADER_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('address',''))" 2>/dev/null)
            LEADER_PORT=$(echo "$LEADER_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('port',8000))" 2>/dev/null)
            if [ -n "$LEADER_ADDRESS" ]; then
                echo "${LEADER_ADDRESS}:${LEADER_PORT}"
                return 0
            fi
        fi
    done
    return 1
}

# Descubrir todos los nodos del servicio Docker Swarm
discover_swarm_nodes() {
    # Resolver tasks.node para obtener todas las IPs de los contenedores
    getent hosts ${NODE_SERVICE} 2>/dev/null | awk '{print $1}' || true
}

# Generar configuración de fallback cuando no hay nodos disponibles
generate_fallback_config() {
    cat > "${UPSTREAM_DIR}/slaves.conf" << EOF
# Fallback configuration - no nodes available
upstream slave_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

upstream slave_frontend {
    server 127.0.0.1:80;
    keepalive 8;
}

upstream master_api {
    server 127.0.0.1:8000;
    keepalive 8;
}
EOF
    log "Generated fallback configuration"
}

# Generar configuración HA con todos los nodos descubiertos
generate_ha_upstream_config() {
    local nodes=("$@")
    local config_file="${UPSTREAM_DIR}/slaves.conf"
    
    {
        echo "# HA Mode - Generated upstream configuration"
        echo "# Generated at: $(date)"
        echo "# Nodes discovered: ${#nodes[@]}"
        echo ""
        
        # API upstream - todos los nodos pueden servir la API
        echo "upstream slave_api {"
        echo "    least_conn;"
        for node in "${nodes[@]}"; do
            echo "    server ${node}:${NODE_PORT} max_fails=3 fail_timeout=30s;"
        done
        echo "    keepalive 32;"
        echo "}"
        echo ""
        
        # Frontend upstream - todos los nodos sirven el frontend
        echo "upstream slave_frontend {"
        echo "    least_conn;"
        for node in "${nodes[@]}"; do
            echo "    server ${node}:80 max_fails=3 fail_timeout=30s;"
        done
        echo "    keepalive 16;"
        echo "}"
        echo ""
        
        # Master API upstream - el líder actual (con fallback a todos los nodos)
        # En HA, cualquier nodo puede responder /api/v1/cluster/master para redirigir
        echo "upstream master_api {"
        echo "    least_conn;"
        for node in "${nodes[@]}"; do
            echo "    server ${node}:${NODE_PORT} max_fails=2 fail_timeout=10s;"
        done
        echo "    keepalive 8;"
        echo "}"
        
    } > "$config_file"
    
    log "Generated HA upstream configuration with ${#nodes[@]} nodes"
    return 0
}

generate_upstreams() {
    log "Fetching active nodes..."
    
    # En modo HA, descubrimos los nodos del servicio Docker Swarm
    if [ "$HA_MODE" = "true" ]; then
        log "HA Mode: Discovering nodes from Swarm service ${NODE_SERVICE}"
        
        NODE_IPS=$(discover_swarm_nodes)
        if [ -z "$NODE_IPS" ]; then
            log "WARNING: No nodes discovered from Swarm service"
            generate_fallback_config
            return 1
        fi
        
        # Convertir a array
        IFS=$'\n' read -rd '' -a NODES_ARRAY <<< "$NODE_IPS" || true
        log "Discovered ${#NODES_ARRAY[@]} node(s): ${NODES_ARRAY[*]}"
        
        # Descubrir el líder actual
        LEADER=$(discover_leader "${NODES_ARRAY[@]}")
        if [ -n "$LEADER" ]; then
            log "Current Raft leader: $LEADER"
        else
            log "WARNING: Could not determine Raft leader, using first node as reference"
            LEADER="${NODES_ARRAY[0]}:${NODE_PORT}"
        fi
        
        # Generar configuración con todos los nodos descubiertos
        generate_ha_upstream_config "${NODES_ARRAY[@]}"
        return $?
    fi
    
    # Modo legacy: consultar al master fijo
    log "Legacy Mode: Fetching nodes from master ${MASTER_HOST}:${MASTER_PORT}"
    
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
# Initial configuration - waiting for nodes to register
upstream slave_api {
    server 127.0.0.1:8000;
    keepalive 16;
}

upstream slave_frontend {
    server 127.0.0.1:80;
    keepalive 8;
}

upstream master_api {
    server 127.0.0.1:8000;
    keepalive 8;
}
EOF

log "Starting upstream update daemon (interval: ${UPDATE_INTERVAL}s, HA_MODE: ${HA_MODE})"

# Loop principal
while true; do
    if generate_upstreams; then
        reload_nginx
    fi
    sleep "$UPDATE_INTERVAL"
done

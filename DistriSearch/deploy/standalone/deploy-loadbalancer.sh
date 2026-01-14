#!/bin/bash
# ============================================================================
# deploy-loadbalancer.sh - Desplegar Load Balancer en cada máquina
# ============================================================================
# El Load Balancer (Nginx) proporciona:
# - Punto de entrada en puerto 443 (HTTPS)
# - Balanceo de carga entre los nodos locales y remotos
# - SSL termination
#
# ARQUITECTURA:
# - Se despliega UNO en cada máquina para redundancia
# - Cada Load Balancer conoce TODOS los nodos del cluster
# - Si una máquina queda aislada, su LB sigue sirviendo los nodos locales
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Valores por defecto
CONTAINER_NAME="distrisearch-loadbalancer"
IMAGE_NAME="distrisearch/loadbalancer:latest"
HTTP_PORT="80"
HTTPS_PORT="443"
NETWORK_NAME="distrisearch-network"  # Red overlay por defecto

# IPs de las máquinas
MACHINE_A_IP="192.168.61.32"
MACHINE_B_IP="192.168.61.33"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    echo ""
    echo -e "${BLUE}USO:${NC}"
    echo "  $0 [opciones]"
    echo ""
    echo -e "${BLUE}OPCIONES:${NC}"
    echo "  --http-port       Puerto HTTP (default: 80)"
    echo "  --https-port      Puerto HTTPS (default: 443)"
    echo "  --network, -n     Red Docker a conectar (default: distrisearch-network)"
    echo "  --no-overlay      No conectar a red overlay"
    echo "  --rebuild         Reconstruir imagen antes de desplegar"
    echo "  --help, -h        Mostrar esta ayuda"
    echo ""
    exit 0
}

# Parsear argumentos
REBUILD=false
USE_OVERLAY=true
while [[ $# -gt 0 ]]; do
    case $1 in
        --http-port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --https-port)
            HTTPS_PORT="$2"
            shift 2
            ;;
        --network|-n)
            NETWORK_NAME="$2"
            shift 2
            ;;
        --no-overlay)
            USE_OVERLAY=false
            NETWORK_NAME=""
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            shift
            ;;
    esac
done

# Detectar IP local
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           DESPLEGAR LOAD BALANCER (Nginx)                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Configuración:"
echo "   Contenedor:   $CONTAINER_NAME"
echo "   Puerto HTTP:  $HTTP_PORT"
echo "   Puerto HTTPS: $HTTPS_PORT"
echo "   IP Local:     $LOCAL_IP"
echo "   Red:          ${NETWORK_NAME:-ninguna (bridge)}"
echo ""

# ============================================================================
# Generar configuración de upstreams dinámicos
# ============================================================================
generate_upstreams() {
    log_info "Detectando nodos activos en la red..."
    
    UPSTREAM_DIR="${PROJECT_ROOT}/docker/load-balancer/conf.d/upstreams"
    mkdir -p "$UPSTREAM_DIR"
    
    # Detectar contenedores distrisearch-node-* activos
    ACTIVE_NODES=$(docker ps --format '{{.Names}}' | grep "^distrisearch-node-node-" | sed 's/distrisearch-node-//' | sort)
    
    if [ -z "$ACTIVE_NODES" ]; then
        log_warn "No se encontraron nodos activos. Usando configuración por defecto (node-1, node-2)"
        ACTIVE_NODES="node-1
node-2"
    fi
    
    log_info "Nodos detectados:"
    echo "$ACTIVE_NODES" | while read node; do
        echo "   - $node"
    done
    
    # Generar líneas de servidor para API (puerto 8000)
    API_SERVERS=""
    FRONTEND_SERVERS=""
    while read node; do
        if [ -n "$node" ]; then
            API_SERVERS="${API_SERVERS}    server ${node}:8000 max_fails=3 fail_timeout=10s;
"
            FRONTEND_SERVERS="${FRONTEND_SERVERS}    server ${node}:80 max_fails=3 fail_timeout=10s;
"
        fi
    done <<< "$ACTIVE_NODES"
    
    # Generar configuración de upstreams
    cat > "${UPSTREAM_DIR}/nodes.conf" << EOF
# Upstream generado automáticamente - $(date)
# Nodos detectados: $(echo $ACTIVE_NODES | tr '\n' ' ')

# API endpoints - todos los nodos activos
upstream node_api {
    least_conn;
${API_SERVERS}    keepalive 16;
}

# Frontend endpoints
upstream node_frontend {
    least_conn;
${FRONTEND_SERVERS}    keepalive 8;
}

# Para compatibilidad con configuración existente
upstream master_api {
    least_conn;
${API_SERVERS}    keepalive 16;
}

upstream slave_api {
    least_conn;
${API_SERVERS}    keepalive 16;
}

upstream slave_frontend {
    least_conn;
${FRONTEND_SERVERS}    keepalive 8;
}
EOF

    log_info "Configuración de upstreams generada con $(echo "$ACTIVE_NODES" | wc -l) nodos"
}

# ============================================================================
# Generar certificados SSL auto-firmados
# ============================================================================
generate_ssl() {
    SSL_DIR="${PROJECT_ROOT}/docker/load-balancer/ssl"
    
    if [ ! -f "${SSL_DIR}/server.crt" ]; then
        log_info "Generando certificados SSL auto-firmados..."
        mkdir -p "$SSL_DIR"
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "${SSL_DIR}/server.key" \
            -out "${SSL_DIR}/server.crt" \
            -subj "/C=ES/ST=State/L=City/O=DistriSearch/OU=Dev/CN=distrisearch.local" \
            2>/dev/null
            
        log_info "Certificados SSL generados"
    else
        log_info "Usando certificados SSL existentes"
    fi
}

# ============================================================================
# Construir imagen
# ============================================================================
build_image() {
    if [ "$REBUILD" = true ] || ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "distrisearch/loadbalancer"; then
        log_info "Construyendo imagen Load Balancer..."
        
        cd "$PROJECT_ROOT"
        docker build -t "$IMAGE_NAME" -f docker/load-balancer/Dockerfile docker/load-balancer/
        
        log_info "✅ Imagen construida: $IMAGE_NAME"
    else
        log_info "Usando imagen existente: $IMAGE_NAME"
    fi
}

# ============================================================================
# Desplegar contenedor
# ============================================================================
deploy_container() {
    # Detener contenedor existente
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "Deteniendo contenedor existente..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    fi
    
    log_info "Iniciando contenedor Load Balancer..."
    
    # Construir comando docker run
    DOCKER_CMD="docker run -d --name $CONTAINER_NAME"
    DOCKER_CMD="$DOCKER_CMD --hostname loadbalancer-$(hostname -s)"
    DOCKER_CMD="$DOCKER_CMD -p ${HTTP_PORT}:80"
    DOCKER_CMD="$DOCKER_CMD -p ${HTTPS_PORT}:443"
    DOCKER_CMD="$DOCKER_CMD -p 8080:8080"  # Status endpoint
    
    # Variables de entorno para supervisord
    DOCKER_CMD="$DOCKER_CMD -e HA_MODE=active"
    DOCKER_CMD="$DOCKER_CMD -e NODE_SERVICE=distrisearch-node"
    DOCKER_CMD="$DOCKER_CMD -e NODE_PORT=8000"
    DOCKER_CMD="$DOCKER_CMD -e UPDATE_INTERVAL=30"
    
    # Montar configuraciones
    DOCKER_CMD="$DOCKER_CMD -v ${PROJECT_ROOT}/docker/load-balancer/conf.d/upstreams:/etc/nginx/conf.d/upstreams:ro"
    
    # Montar SSL si existe
    SSL_DIR="${PROJECT_ROOT}/docker/load-balancer/ssl"
    if [ -d "$SSL_DIR" ]; then
        DOCKER_CMD="$DOCKER_CMD -v ${SSL_DIR}:/etc/nginx/ssl:ro"
    fi
    
    # Conectar a red overlay si se especificó y existe
    if [ -n "$NETWORK_NAME" ] && [ "$USE_OVERLAY" = true ]; then
        if docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
            DOCKER_CMD="$DOCKER_CMD --network $NETWORK_NAME"
            log_info "Conectando a red overlay: $NETWORK_NAME"
        else
            log_warn "Red overlay '$NETWORK_NAME' no existe, usando red bridge"
        fi
    fi
    
    DOCKER_CMD="$DOCKER_CMD --restart=no"
    DOCKER_CMD="$DOCKER_CMD $IMAGE_NAME"
    
    # Ejecutar
    eval $DOCKER_CMD
    
    # Verificar
    sleep 3
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "✅ Load Balancer iniciado correctamente"
    else
        log_error "❌ Error iniciando Load Balancer"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        exit 1
    fi
}

# ============================================================================
# Verificar funcionamiento
# ============================================================================
verify_lb() {
    log_info "Verificando Load Balancer..."
    
    # Esperar a que esté listo
    sleep 2
    
    # Probar endpoint de salud
    if curl -sf "http://localhost:${HTTP_PORT}/health" > /dev/null 2>&1; then
        log_info "✅ Load Balancer respondiendo en puerto $HTTP_PORT"
    else
        log_warn "⚠️  Load Balancer puede no estar completamente listo"
    fi
}

# ============================================================================
# Main
# ============================================================================
generate_upstreams
generate_ssl
build_image
deploy_container
verify_lb

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              LOAD BALANCER DESPLEGADO                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Contenedor:    $CONTAINER_NAME"
echo "  Puerto HTTP:   $HTTP_PORT"
echo "  Puerto HTTPS:  $HTTPS_PORT"
echo "  Status:        http://localhost:8080/nginx_status"
echo ""
echo "  URLs de acceso:"
echo "    http://${LOCAL_IP}:${HTTP_PORT}"
echo "    https://${LOCAL_IP}:${HTTPS_PORT}"
echo ""
echo "  Comandos:"
echo "    Ver logs:    docker logs -f $CONTAINER_NAME"
echo "    Detener:     docker stop $CONTAINER_NAME"
echo "    Eliminar:    docker rm -f $CONTAINER_NAME"
echo ""

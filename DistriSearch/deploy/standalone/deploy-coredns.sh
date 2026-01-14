#!/bin/bash
# ============================================================================
# deploy-coredns.sh - Desplegar CoreDNS como respaldo de DNS
# ============================================================================
# CoreDNS proporciona resolución DNS de respaldo cuando el DNS de Docker
# falla (por ejemplo, durante particiones de red).
#
# Se despliega UNO en cada máquina para tolerancia a fallos.
# Se conecta a la red overlay de Swarm para comunicación entre máquinas.
#
# USO:
#   ./deploy-coredns.sh                    # Desplegar CoreDNS en red overlay
#   ./deploy-coredns.sh --no-overlay       # Desplegar sin red overlay
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Valores por defecto
CONTAINER_NAME="distrisearch-coredns"
IMAGE_NAME="distrisearch/coredns:latest"
DNS_PORT="5353"
NETWORK_NAME="distrisearch-network"  # Red overlay por defecto

# IPs de las máquinas
MACHINE_A_IP="192.168.1.11"
MACHINE_B_IP="192.168.1.13"

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
echo -e "${BLUE}║              DESPLEGAR COREDNS (DNS BACKUP)                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Configuración:"
echo "   Contenedor:   $CONTAINER_NAME"
echo "   Puerto DNS:   $DNS_PORT"
echo "   IP Local:     $LOCAL_IP"
echo "   Red:          ${NETWORK_NAME:-ninguna (host)}"
echo ""

# ============================================================================
# Crear zona DNS actualizada con IPs correctas
# ============================================================================
create_zone_file() {
    log_info "Generando archivo de zona DNS..."
    
    ZONE_DIR="${PROJECT_ROOT}/docker/coredns/zones"
    mkdir -p "$ZONE_DIR"
    
    cat > "${ZONE_DIR}/distrisearch.local.zone" << EOF
; ═══════════════════════════════════════════════════════════════════════════
; DistriSearch Zone File - Generado automáticamente
; Fecha: $(date)
; ═══════════════════════════════════════════════════════════════════════════

\$ORIGIN distrisearch.local.
\$TTL 30

@       IN      SOA     ns1.distrisearch.local. admin.distrisearch.local. (
                        $(date +%Y%m%d%H)   ; Serial
                        3600                ; Refresh (1 hour)
                        600                 ; Retry (10 minutes)
                        86400               ; Expire (1 day)
                        30                  ; Minimum TTL
                        )

; Name servers
@       IN      NS      ns1.distrisearch.local.
ns1     IN      A       ${LOCAL_IP}

; ═══════════════════════════════════════════════════════════════════════════
; NODOS - Direcciones de los nodos DistriSearch
; ═══════════════════════════════════════════════════════════════════════════

; Nodos en Máquina A (richard-VirtualBox)
node-1          IN      A       ${MACHINE_A_IP}
node-2          IN      A       ${MACHINE_A_IP}

; Nodo en Máquina B (abel-VirtualBox)
node-3          IN      A       ${MACHINE_B_IP}

; Alias genérico para nodos (round-robin)
node            IN      A       ${MACHINE_A_IP}
node            IN      A       ${MACHINE_A_IP}
node            IN      A       ${MACHINE_B_IP}

; ═══════════════════════════════════════════════════════════════════════════
; SERVICIOS - Load Balancer y DNS
; ═══════════════════════════════════════════════════════════════════════════

; Load Balancers (uno en cada máquina)
lb              IN      A       ${MACHINE_A_IP}
lb              IN      A       ${MACHINE_B_IP}
loadbalancer    IN      A       ${MACHINE_A_IP}
loadbalancer    IN      A       ${MACHINE_B_IP}

; DNS (CoreDNS en cada máquina)
dns             IN      A       ${MACHINE_A_IP}
dns             IN      A       ${MACHINE_B_IP}
coredns         IN      A       ${LOCAL_IP}

; Entrada principal (apunta a load balancers)
www             IN      CNAME   lb.distrisearch.local.
@               IN      A       ${MACHINE_A_IP}
@               IN      A       ${MACHINE_B_IP}

; ═══════════════════════════════════════════════════════════════════════════
; SRV RECORDS para descubrimiento de servicios
; ═══════════════════════════════════════════════════════════════════════════

; API de nodos (puerto específico de cada nodo)
_api._tcp.node-1    IN      SRV     10 50 8001 node-1.distrisearch.local.
_api._tcp.node-2    IN      SRV     10 50 8002 node-2.distrisearch.local.
_api._tcp.node-3    IN      SRV     10 50 8003 node-3.distrisearch.local.

; Load Balancer HTTPS (puerto 443)
_https._tcp         IN      SRV     10 50 443 lb.distrisearch.local.

; DNS (puerto 5353)
_dns._udp           IN      SRV     10 50 5353 coredns.distrisearch.local.
EOF

    log_info "Archivo de zona creado: ${ZONE_DIR}/distrisearch.local.zone"
}

# ============================================================================
# Construir imagen CoreDNS
# ============================================================================
build_image() {
    if [ "$REBUILD" = true ] || ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "$IMAGE_NAME"; then
        log_info "Construyendo imagen CoreDNS..."
        
        cd "$PROJECT_ROOT"
        docker build -t "$IMAGE_NAME" -f docker/coredns/Dockerfile docker/coredns/
        
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
    
    log_info "Iniciando contenedor CoreDNS..."
    
    # Construir comando docker run
    DOCKER_CMD="docker run -d --name $CONTAINER_NAME"
    DOCKER_CMD="$DOCKER_CMD --hostname coredns-$(hostname -s)"
    DOCKER_CMD="$DOCKER_CMD -p ${DNS_PORT}:5353/udp"
    DOCKER_CMD="$DOCKER_CMD -p ${DNS_PORT}:5353/tcp"
    DOCKER_CMD="$DOCKER_CMD -p 9153:9153"  # Prometheus metrics
    
    # Montar zonas actualizadas
    DOCKER_CMD="$DOCKER_CMD -v ${PROJECT_ROOT}/docker/coredns/zones:/etc/coredns/zones:ro"
    
    # Conectar a red si se especificó
    if [ -n "$NETWORK_NAME" ]; then
        DOCKER_CMD="$DOCKER_CMD --network $NETWORK_NAME"
    fi
    
    DOCKER_CMD="$DOCKER_CMD --restart=no"
    DOCKER_CMD="$DOCKER_CMD $IMAGE_NAME"
    
    # Ejecutar
    eval $DOCKER_CMD
    
    # Verificar
    sleep 2
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "✅ CoreDNS iniciado correctamente"
    else
        log_error "❌ Error iniciando CoreDNS"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        exit 1
    fi
}

# ============================================================================
# Verificar funcionamiento
# ============================================================================
verify_dns() {
    log_info "Verificando resolución DNS..."
    
    # Esperar a que esté listo
    sleep 3
    
    # Probar resolución
    if command -v dig &> /dev/null; then
        RESULT=$(dig @127.0.0.1 -p ${DNS_PORT} node-1.distrisearch.local +short 2>/dev/null)
        if [ -n "$RESULT" ]; then
            log_info "✅ DNS funcionando: node-1.distrisearch.local -> $RESULT"
        else
            log_warn "⚠️  No se pudo resolver node-1.distrisearch.local"
        fi
    else
        log_warn "dig no instalado, saltando verificación"
    fi
}

# ============================================================================
# Main
# ============================================================================
create_zone_file
build_image
deploy_container
verify_dns

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  COREDNS DESPLEGADO                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Contenedor:    $CONTAINER_NAME"
echo "  Puerto DNS:    ${DNS_PORT}/udp y ${DNS_PORT}/tcp"
echo "  Metrics:       http://localhost:9153/metrics"
echo ""
echo "  Probar DNS:"
echo "    dig @127.0.0.1 -p ${DNS_PORT} node-1.distrisearch.local"
echo "    dig @127.0.0.1 -p ${DNS_PORT} lb.distrisearch.local"
echo ""
echo "  Comandos:"
echo "    Ver logs:    docker logs -f $CONTAINER_NAME"
echo "    Detener:     docker stop $CONTAINER_NAME"
echo "    Eliminar:    docker rm -f $CONTAINER_NAME"
echo ""

#!/bin/bash
# ============================================================================
# deploy-machine-a.sh - Desplegar TODO en Máquina A (richard-VirtualBox)
# ============================================================================
# Esta máquina aloja:
# - Node-1 y Node-2 (nodos de aplicación)
# - CoreDNS (backup DNS)
# - Load Balancer (entrada HTTPS en puerto 443)
#
# IP: 192.168.1.11
#
# ARQUITECTURA:
# - Los contenedores se conectan a la red overlay de Swarm
# - Cada componente es autónomo y sobrevive particiones de red
# - Los nodos NO se reinician automáticamente (restart=no)
#
# PREREQUISITOS:
# 1. Docker Swarm inicializado (este debe ser el manager o haber hecho join)
# 2. Red overlay creada: ./init-swarm-network.sh (desde el manager)
# 3. Imagen construida: ./build-image.sh
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     DESPLEGAR MÁQUINA A (richard-VirtualBox)                  ║${NC}"
echo -e "${BLUE}║     Componentes: Node-1, Node-2, CoreDNS, Load Balancer       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuración de red
MACHINE_A_IP="192.168.61.32"
MACHINE_B_IP="192.168.61.33"
PEERS="${MACHINE_A_IP}:8001,${MACHINE_A_IP}:8002,${MACHINE_B_IP}:8003"
NETWORK_NAME="distrisearch-network"

# Verificar Swarm
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    log_error "Este nodo no es parte de un Docker Swarm"
    log_info "Ejecuta 'docker swarm init' o 'docker swarm join' primero"
    exit 1
fi

# Verificar red overlay
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    log_warn "Red overlay '$NETWORK_NAME' no encontrada"
    log_info "Creando red overlay (si somos manager)..."
    
    if docker info --format '{{.Swarm.ControlAvailable}}' | grep -q "true"; then
        docker network create --driver overlay --attachable --subnet "10.10.0.0/24" "$NETWORK_NAME" || true
    else
        log_error "La red debe crearse desde el manager: ./init-swarm-network.sh"
        exit 1
    fi
fi

# ============================================================================
# 1. Desplegar CoreDNS (Backup DNS)
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[1/4] Desplegando CoreDNS (Backup DNS)..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-coredns.sh" --network "$NETWORK_NAME"

echo ""

# ============================================================================
# 2. Desplegar Load Balancer
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[2/4] Desplegando Load Balancer..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-loadbalancer.sh" --network "$NETWORK_NAME"

echo ""

# ============================================================================
# 3. Desplegar Nodo 1
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[3/4] Desplegando Node-1..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-node.sh" \
    --node-id node-1 \
    --api-port 8001 \
    --http-port 8081 \
    --https-port 4431 \
    --peers "$PEERS" \
    --network "$NETWORK_NAME"

echo ""

# ============================================================================
# 4. Desplegar Nodo 2
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[4/4] Desplegando Node-2..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-node.sh" \
    --node-id node-2 \
    --api-port 8002 \
    --http-port 8082 \
    --https-port 4432 \
    --peers "$PEERS" \
    --network "$NETWORK_NAME"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              MÁQUINA A DESPLEGADA COMPLETAMENTE               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Componentes activos en esta máquina:"
echo ""
echo "  📡 CoreDNS (Backup DNS):"
echo "      Puerto: 5353 (UDP/TCP)"
echo "      Test:   dig @127.0.0.1 -p 5353 distrisearch.local"
echo ""
echo "  🔀 Load Balancer:"
echo "      HTTP:   http://${MACHINE_A_IP}:80"
echo "      HTTPS:  https://${MACHINE_A_IP}:443"
echo ""
echo "  🖥️  Node-1:"
echo "      API:      http://${MACHINE_A_IP}:8001"
echo "      Frontend: http://${MACHINE_A_IP}:8081"
echo ""
echo "  🖥️  Node-2:"
echo "      API:      http://${MACHINE_A_IP}:8002"
echo "      Frontend: http://${MACHINE_A_IP}:8082"
echo ""
echo "  Red Overlay: $NETWORK_NAME"
echo ""
echo "  ═══════════════════════════════════════════════════════════════"
echo "  COMANDOS PARA CONTROL MANUAL:"
echo "  ═══════════════════════════════════════════════════════════════"
echo ""
echo "    # Ver estado de todos los contenedores"
echo "    docker ps | grep distrisearch"
echo ""
echo "    # Detener un nodo (simular caída)"
echo "    docker stop distrisearch-node-node-1"
echo "    docker stop distrisearch-node-node-2"
echo ""
echo "    # Reiniciar un nodo"
echo "    docker start distrisearch-node-node-1"
echo ""
echo "    # Ver logs de un nodo"
echo "    docker logs -f distrisearch-node-node-1"
echo ""
echo "    # Acceso al sistema:"
echo "    https://${MACHINE_A_IP}:443  (via Load Balancer)"
echo ""

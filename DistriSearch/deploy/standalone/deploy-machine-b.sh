#!/bin/bash
# ============================================================================
# deploy-machine-b.sh - Desplegar TODO en Máquina B (abel-VirtualBox)
# ============================================================================
# Esta máquina aloja:
# - Node-3 (nodo de aplicación)
# - CoreDNS (backup DNS)
# - Load Balancer (entrada HTTPS en puerto 443)
#
# IP: 192.168.1.13
#
# ARQUITECTURA:
# - Los contenedores se conectan a la red overlay de Swarm
# - Cada componente es autónomo y sobrevive particiones de red
# - Los nodos NO se reinician automáticamente (restart=no)
#
# PREREQUISITOS:
# 1. Docker Swarm: debe haber hecho 'docker swarm join' al manager
# 2. Red overlay ya existe (creada desde el manager)
# 3. Imagen construida o transferida: ./build-image.sh o ./transfer-image.sh
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
echo -e "${BLUE}║     DESPLEGAR MÁQUINA B (abel-VirtualBox)                     ║${NC}"
echo -e "${BLUE}║     Componentes: Node-3, CoreDNS, Load Balancer               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuración de red
MACHINE_A_IP="192.168.1.11"
MACHINE_B_IP="192.168.1.13"
PEERS="${MACHINE_A_IP}:8001,${MACHINE_A_IP}:8002,${MACHINE_B_IP}:8003"
NETWORK_NAME="distrisearch-network"

# Verificar Swarm
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    log_error "Este nodo no es parte de un Docker Swarm"
    log_info "Ejecuta 'docker swarm join --token <token> <manager-ip>:2377'"
    exit 1
fi

# Verificar que la red overlay existe
# Nota: En workers, la red overlay se ve solo cuando un contenedor la usa
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    log_warn "Red overlay '$NETWORK_NAME' no visible aún"
    log_info "La red se hará visible al conectar el primer contenedor"
fi

# ============================================================================
# 1. Desplegar CoreDNS (Backup DNS)
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[1/3] Desplegando CoreDNS (Backup DNS)..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-coredns.sh" --network "$NETWORK_NAME"

echo ""

# ============================================================================
# 2. Desplegar Load Balancer
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[2/3] Desplegando Load Balancer..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-loadbalancer.sh" --network "$NETWORK_NAME"

echo ""

# ============================================================================
# 3. Desplegar Nodo 3
# ============================================================================
log_info "═══════════════════════════════════════════════════════════════"
log_info "[3/3] Desplegando Node-3..."
log_info "═══════════════════════════════════════════════════════════════"
"$SCRIPT_DIR/deploy-node.sh" \
    --node-id node-3 \
    --api-port 8003 \
    --http-port 8083 \
    --https-port 4433 \
    --peers "$PEERS" \
    --network "$NETWORK_NAME"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              MÁQUINA B DESPLEGADA COMPLETAMENTE               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Componentes activos en esta máquina:"
echo ""
echo "  📡 CoreDNS (Backup DNS):"
echo "      Puerto: 5353 (UDP/TCP)"
echo "      Test:   dig @127.0.0.1 -p 5353 distrisearch.local"
echo ""
echo "  🔀 Load Balancer:"
echo "      HTTP:   http://${MACHINE_B_IP}:80"
echo "      HTTPS:  https://${MACHINE_B_IP}:443"
echo ""
echo "  🖥️  Node-3:"
echo "      API:      http://${MACHINE_B_IP}:8003"
echo "      Frontend: http://${MACHINE_B_IP}:8083"
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
echo "    # Detener el nodo (simular caída)"
echo "    docker stop distrisearch-node-node-3"
echo ""
echo "    # Reiniciar el nodo"
echo "    docker start distrisearch-node-node-3"
echo ""
echo "    # Ver logs del nodo"
echo "    docker logs -f distrisearch-node-node-3"
echo ""
echo "    # Acceso al sistema:"
echo "    https://${MACHINE_B_IP}:443  (via Load Balancer)"
echo ""

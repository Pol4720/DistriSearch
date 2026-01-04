#!/bin/bash
# ============================================================================
# 03-join-swarm.sh - Une un nodo worker al cluster Swarm
# ============================================================================
# Ejecutar en cada máquina WORKER
# Uso: ./03-join-swarm.sh <MANAGER_IP> <TOKEN>
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Unir Nodo al Swarm"
echo "=============================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# 1. Obtener parámetros
# ============================================================================
MANAGER_IP=$1
TOKEN=$2

if [ -z "$MANAGER_IP" ] || [ -z "$TOKEN" ]; then
    echo "Uso: $0 <MANAGER_IP> <TOKEN>"
    echo ""
    echo "Ejemplo:"
    echo "  $0 192.168.1.10 SWMTKN-1-xxx..."
    echo ""
    echo "El token y la IP te los proporciona el manager al ejecutar 02-init-swarm.sh"
    exit 1
fi

# ============================================================================
# 2. Verificar Docker
# ============================================================================
if ! docker info &> /dev/null; then
    log_error "Docker no está funcionando. Ejecuta primero 01-prepare-node.sh"
    exit 1
fi

# ============================================================================
# 3. Verificar conectividad con el manager
# ============================================================================
log_info "Verificando conectividad con el manager ($MANAGER_IP)..."

if ! ping -c 1 -W 3 $MANAGER_IP &> /dev/null; then
    log_error "No se puede conectar con el manager en $MANAGER_IP"
    echo "Verifica:"
    echo "  - Que el manager está encendido"
    echo "  - Que ambas máquinas están en la misma red"
    echo "  - Que el firewall permite la conexión"
    exit 1
fi

log_info "Conectividad OK"

# ============================================================================
# 4. Verificar puerto Swarm
# ============================================================================
log_info "Verificando puerto Swarm (2377)..."

if nc -z -w3 $MANAGER_IP 2377 2>/dev/null; then
    log_info "Puerto 2377 accesible"
else
    log_warn "No se puede verificar el puerto 2377 (nc no instalado o puerto bloqueado)"
    log_warn "Continuando de todos modos..."
fi

# ============================================================================
# 5. Verificar estado actual
# ============================================================================
SWARM_STATUS=$(docker info --format '{{.Swarm.LocalNodeState}}')
if [ "$SWARM_STATUS" == "active" ]; then
    log_warn "Este nodo ya es parte de un Swarm"
    read -p "¿Deseas abandonar el Swarm actual y unirte al nuevo? (s/n): " confirm
    if [ "$confirm" == "s" ]; then
        docker swarm leave --force
    else
        exit 0
    fi
fi

# ============================================================================
# 6. Unirse al Swarm
# ============================================================================
log_info "Uniendo nodo al Swarm..."

docker swarm join --token $TOKEN $MANAGER_IP:2377

# ============================================================================
# 7. Verificar
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Nodo Unido al Swarm Correctamente${NC}"
echo "=============================================="
echo ""
log_info "Estado local del nodo:"
docker info --format 'Swarm: {{.Swarm.LocalNodeState}}'
docker info --format 'Manager: {{.Swarm.ControlAvailable}}'
docker info --format 'NodeID: {{.Swarm.NodeID}}'
echo ""
echo "Próximos pasos:"
echo "  1. Repetir este proceso en todos los workers"
echo "  2. En el MANAGER, verificar con: docker node ls"
echo "  3. En el MANAGER, ejecutar 05-deploy-master.sh"

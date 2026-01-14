#!/bin/bash
# ============================================================================
# init-swarm-network.sh - Inicializar red overlay en Docker Swarm
# ============================================================================
# IMPORTANTE: 
# - Docker Swarm se usa SOLO para la red overlay (comunicación entre máquinas)
# - NO usamos docker service, usamos docker run para los contenedores
# - Cada contenedor se conecta a la red overlay pero se gestiona manualmente
#
# Este script debe ejecutarse:
# 1. En el manager del Swarm (una sola vez)
# 2. ANTES de desplegar cualquier contenedor
# ============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

NETWORK_NAME="distrisearch-network"
SUBNET="10.10.0.0/24"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     INICIALIZACIÓN DE RED OVERLAY SWARM                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar si estamos en un Swarm
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    log_error "Este nodo no es parte de un Docker Swarm"
    log_info "Ejecuta 'docker swarm init' o 'docker swarm join' primero"
    exit 1
fi

# Verificar si somos manager
if ! docker info --format '{{.Swarm.ControlAvailable}}' | grep -q "true"; then
    log_error "Este comando debe ejecutarse en un nodo MANAGER del Swarm"
    log_info "La red overlay solo puede crearse desde un manager"
    exit 1
fi

log_info "Nodo Swarm detectado: $(docker info --format '{{.Name}}')"
log_info "Rol: Manager"

# Verificar si la red ya existe
if docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    log_warn "La red '$NETWORK_NAME' ya existe"
    
    # Mostrar información de la red
    echo ""
    log_info "Información de la red existente:"
    docker network inspect "$NETWORK_NAME" --format '
  Nombre: {{.Name}}
  Driver: {{.Driver}}
  Scope:  {{.Scope}}
  Subnet: {{range .IPAM.Config}}{{.Subnet}}{{end}}
  Contenedores: {{range $id, $container := .Containers}}
    - {{$container.Name}} ({{$container.IPv4Address}}){{end}}'
    
    echo ""
    read -p "¿Deseas recrear la red? (y/N): " recreate
    if [[ "$recreate" =~ ^[Yy]$ ]]; then
        log_warn "Eliminando red existente..."
        docker network rm "$NETWORK_NAME" 2>/dev/null || true
    else
        log_info "Manteniendo red existente"
        exit 0
    fi
fi

# Crear la red overlay con attachable=true para docker run
log_info "Creando red overlay '${NETWORK_NAME}'..."
log_info "Subnet: ${SUBNET}"
log_info "Driver: overlay (attachable)"

docker network create \
    --driver overlay \
    --attachable \
    --subnet "$SUBNET" \
    --opt encrypted=true \
    "$NETWORK_NAME"

log_info "✅ Red overlay creada exitosamente"

# Verificar
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              RED OVERLAY CREADA                               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Red:       $NETWORK_NAME"
echo "  Subnet:    $SUBNET"
echo "  Driver:    overlay"
echo "  Attachable: true (permite docker run --network)"
echo "  Encrypted: true"
echo ""
echo "  IMPORTANTE:"
echo "  - Esta red permite comunicación entre máquinas del Swarm"
echo "  - Los contenedores deben usar: --network $NETWORK_NAME"
echo "  - La red es compartida por TODOS los nodos del Swarm"
echo ""
echo "  Siguiente paso:"
echo "    En Máquina A: ./deploy-machine-a.sh"
echo "    En Máquina B: ./deploy-machine-b.sh"
echo ""

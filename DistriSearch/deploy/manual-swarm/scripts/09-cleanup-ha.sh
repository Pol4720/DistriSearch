#!/bin/bash
# ============================================================================
# 09-cleanup-ha.sh - Limpiar despliegue HA
# ============================================================================
# Elimina todos los servicios y recursos del cluster HA
#
# Uso: ./09-cleanup-ha.sh [--volumes] [--network] [--all]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Limpiar Cluster HA"
echo "=============================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# Parsear argumentos
# ============================================================================
CLEAN_VOLUMES=false
CLEAN_NETWORK=false
CLEAN_ALL=false

for arg in "$@"; do
    case $arg in
        --volumes)
            CLEAN_VOLUMES=true
            ;;
        --network)
            CLEAN_NETWORK=true
            ;;
        --all)
            CLEAN_ALL=true
            CLEAN_VOLUMES=true
            CLEAN_NETWORK=true
            ;;
    esac
done

# ============================================================================
# Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

# ============================================================================
# Confirmación
# ============================================================================
echo ""
echo -e "${YELLOW}Este script eliminará:${NC}"
echo "  • Todos los servicios distrisearch-node-*"
echo "  • Todos los servicios node*-mongodb y node*-redis"
echo "  • Servicios de infraestructura (load-balancer, coredns, coordinator-redis)"

if [ "$CLEAN_VOLUMES" = true ]; then
    echo "  • Todos los volúmenes de datos (node*-*)"
fi
if [ "$CLEAN_NETWORK" = true ]; then
    echo "  • Red overlay distrisearch-network"
fi

echo ""
read -p "¿Estás seguro de continuar? (s/n): " confirm
if [ "$confirm" != "s" ]; then
    echo "Cancelado"
    exit 0
fi

# ============================================================================
# Eliminar servicios de nodos
# ============================================================================
echo ""
log_info "Eliminando servicios de nodos DistriSearch..."

docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-" | while read svc; do
    docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc" || true
done

# ============================================================================
# Eliminar MongoDB y Redis de nodos
# ============================================================================
log_info "Eliminando servicios MongoDB y Redis de nodos..."

docker service ls --format "{{.Name}}" | grep -E "^node[0-9]+-mongodb|^node[0-9]+-redis" | while read svc; do
    docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc" || true
done

# También limpiar formato antiguo (slave*)
docker service ls --format "{{.Name}}" | grep -E "^slave[0-9]|^distrisearch-slave|^distrisearch-master" | while read svc; do
    docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc" || true
done

# ============================================================================
# Eliminar infraestructura
# ============================================================================
log_info "Eliminando servicios de infraestructura..."

for svc in load-balancer coredns coordinator-redis master-redis; do
    if docker service inspect "$svc" &>/dev/null; then
        docker service rm "$svc" && echo "  Eliminado: $svc"
    fi
done

# ============================================================================
# Eliminar volúmenes si se solicitó
# ============================================================================
if [ "$CLEAN_VOLUMES" = true ]; then
    log_info "Eliminando volúmenes de datos..."
    sleep 5  # Esperar a que los servicios se detengan
    
    docker volume ls --format "{{.Name}}" | grep -E "^node[0-9]+-|^slave[0-9]+-|^master-|^coordinator-" | while read vol; do
        docker volume rm "$vol" 2>/dev/null && echo "  Eliminado: $vol" || true
    done
fi

# ============================================================================
# Eliminar red si se solicitó
# ============================================================================
if [ "$CLEAN_NETWORK" = true ]; then
    log_info "Eliminando red overlay..."
    sleep 3
    
    docker network rm distrisearch-network 2>/dev/null && echo "  Eliminada: distrisearch-network" || true
fi

# ============================================================================
# Resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Limpieza Completada${NC}"
echo "=============================================="
echo ""

echo -e "${CYAN}Estado actual de servicios:${NC}"
docker service ls --format "table {{.Name}}\t{{.Replicas}}" | grep -E "distrisearch|node|redis|coredns|balancer|NAME" || echo "  (ningún servicio DistriSearch)"

echo ""
if [ "$CLEAN_ALL" = true ]; then
    echo "Para redesplegar desde cero:"
    echo "  1. ./02-init-swarm.sh $MANAGER_IP"
    echo "  2. (En workers) docker swarm join ..."
    echo "  3. ./04-deploy-infrastructure-ha.sh"
    echo "  4. ./05-deploy-nodes-ha.sh"
else
    echo "Para redesplegar:"
    echo "  1. ./04-deploy-infrastructure-ha.sh"
    echo "  2. ./05-deploy-nodes-ha.sh"
fi
echo ""

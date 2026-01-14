#!/bin/bash
# ============================================================================
# stop-all.sh - Detener todos los contenedores DistriSearch
# ============================================================================
# Detiene todos los contenedores de DistriSearch en esta máquina:
# - Nodos (distrisearch-node-*)
# - CoreDNS (distrisearch-coredns)
# - Load Balancer (distrisearch-loadbalancer)
# ============================================================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
log_info "Deteniendo todos los contenedores DistriSearch..."

# Buscar y detener todos los contenedores distrisearch-*
CONTAINERS=$(docker ps --format '{{.Names}}' | grep "^distrisearch-" || true)

if [ -z "$CONTAINERS" ]; then
    log_warn "No hay contenedores DistriSearch corriendo"
else
    for container in $CONTAINERS; do
        log_info "Deteniendo: $container"
        docker stop "$container" 2>/dev/null || true
    done
    log_info "✅ Todos los contenedores detenidos"
fi

echo ""
echo "Contenedores detenidos (pueden reiniciarse con docker start):"
docker ps -a --filter "name=distrisearch-" --format "table {{.Names}}\t{{.Status}}"
echo ""

# Preguntar si eliminar
read -p "¿Deseas ELIMINAR los contenedores? (y/N): " remove
if [[ "$remove" =~ ^[Yy]$ ]]; then
    log_info "Eliminando contenedores..."
    STOPPED=$(docker ps -a --format '{{.Names}}' | grep "^distrisearch-" || true)
    for container in $STOPPED; do
        docker rm "$container" 2>/dev/null || true
    done
    log_info "✅ Contenedores eliminados"
fi

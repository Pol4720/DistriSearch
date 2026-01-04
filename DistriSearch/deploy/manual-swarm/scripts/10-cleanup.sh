#!/bin/bash
# ============================================================================
# 10-cleanup.sh - Limpia el despliegue completo
# ============================================================================
# Ejecutar en el MANAGER para eliminar todo el despliegue
# ============================================================================

echo "=============================================="
echo "  DistriSearch - Limpieza del Cluster"
echo "=============================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ============================================================================
# Confirmación
# ============================================================================
echo -e "${RED}¡ADVERTENCIA!${NC}"
echo "Este script eliminará:"
echo "  - Todos los servicios de DistriSearch"
echo "  - Todos los volúmenes de datos"
echo "  - La red overlay"
echo "  - Opcionalmente, el Swarm completo"
echo ""
read -p "¿Estás seguro de que deseas continuar? (escribir 'si' para confirmar): " confirm

if [ "$confirm" != "si" ]; then
    echo "Cancelado."
    exit 0
fi

echo ""

# ============================================================================
# 1. Eliminar servicios
# ============================================================================
log_info "Eliminando servicios..."

SERVICES="distrisearch-frontend distrisearch-slave distrisearch-master redis mongo"

for SERVICE in $SERVICES; do
    if docker service inspect $SERVICE &>/dev/null; then
        docker service rm $SERVICE
        echo "  ✓ $SERVICE eliminado"
    fi
done

# ============================================================================
# 2. Esperar a que los contenedores se detengan
# ============================================================================
log_info "Esperando a que los contenedores se detengan..."
sleep 10

# ============================================================================
# 3. Eliminar volúmenes
# ============================================================================
read -p "¿Eliminar también los volúmenes de datos? (s/n): " delete_volumes

if [ "$delete_volumes" == "s" ]; then
    log_info "Eliminando volúmenes..."
    
    # Volúmenes conocidos
    VOLUMES="mongo-data redis-data"
    for VOL in $VOLUMES; do
        docker volume rm $VOL 2>/dev/null && echo "  ✓ $VOL eliminado" || true
    done
    
    # Volúmenes de slaves
    docker volume ls --format "{{.Name}}" | grep "slave-data" | while read VOL; do
        docker volume rm $VOL 2>/dev/null && echo "  ✓ $VOL eliminado" || true
    done
fi

# ============================================================================
# 4. Eliminar red
# ============================================================================
log_info "Eliminando red overlay..."

if docker network rm distrisearch-network 2>/dev/null; then
    echo "  ✓ Red eliminada"
fi

# ============================================================================
# 5. Opción de eliminar Swarm
# ============================================================================
echo ""
read -p "¿Deseas también destruir el Swarm? (s/n): " destroy_swarm

if [ "$destroy_swarm" == "s" ]; then
    log_warn "Esto desconectará todos los workers del cluster"
    read -p "¿Confirmar destrucción del Swarm? (escribir 'destruir'): " confirm_destroy
    
    if [ "$confirm_destroy" == "destruir" ]; then
        log_info "Abandonando Swarm..."
        docker swarm leave --force
        echo "  ✓ Swarm destruido"
    fi
fi

# ============================================================================
# Resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Limpieza Completada${NC}"
echo "=============================================="
echo ""
echo "Para redesplegar:"
echo "  1. ./02-init-swarm.sh (si destruiste el Swarm)"
echo "  2. ./04-deploy-infrastructure.sh"
echo "  3. ./05-deploy-master.sh"
echo "  4. ./06-deploy-slave.sh"
echo "  5. ./07-deploy-frontend.sh"

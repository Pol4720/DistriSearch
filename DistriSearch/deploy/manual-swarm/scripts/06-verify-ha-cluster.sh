#!/bin/bash
# ============================================================================
# 06-verify-ha-cluster.sh - Verificar estado del cluster HA
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Verificar Cluster HA"
echo "=============================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

# ============================================================================
# 2. Estado del Swarm
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Estado de Docker Swarm${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

echo -e "${CYAN}Nodos del cluster:${NC}"
docker node ls

echo ""
echo -e "${CYAN}Redes overlay:${NC}"
docker network ls --filter driver=overlay

# ============================================================================
# 3. Estado de servicios
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Estado de Servicios${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

echo -e "${CYAN}Todos los servicios:${NC}"
docker service ls --format "table {{.Name}}\t{{.Mode}}\t{{.Replicas}}\t{{.Image}}"

# ============================================================================
# 4. Verificar nodos DistriSearch
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Nodos DistriSearch${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Obtener lista de nodos DistriSearch
DISTRISEARCH_NODES=$(docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-" | sort)

if [ -z "$DISTRISEARCH_NODES" ]; then
    log_warn "No se encontraron nodos DistriSearch desplegados"
    echo "Ejecuta primero: ./05-deploy-nodes-ha.sh"
    exit 0
fi

for NODE in $DISTRISEARCH_NODES; do
    NODE_NUM=$(echo "$NODE" | grep -oE "[0-9]+$")
    API_PORT=$((8000 + NODE_NUM))
    
    echo -e "${CYAN}$NODE:${NC}"
    
    # Estado del servicio
    STATE=$(docker service ps "$NODE" --format "{{.CurrentState}}" 2>/dev/null | head -1)
    if echo "$STATE" | grep -q "Running"; then
        echo -e "  Estado Swarm: ${GREEN}Running${NC}"
    else
        echo -e "  Estado Swarm: ${RED}$STATE${NC}"
        continue
    fi
    
    # Health check API
    HEALTH_URL="http://$MANAGER_IP:$API_PORT/api/v1/health"
    if curl -sf "$HEALTH_URL" --max-time 5 &>/dev/null; then
        echo -e "  API Health:   ${GREEN}OK${NC} ($HEALTH_URL)"
        
        # Intentar obtener rol Raft
        CLUSTER_STATUS=$(curl -sf "http://$MANAGER_IP:$API_PORT/api/v1/cluster/status" --max-time 5 2>/dev/null || echo "{}")
        RAFT_ROLE=$(echo "$CLUSTER_STATUS" | grep -oP '"role"\s*:\s*"\K[^"]+' 2>/dev/null || echo "unknown")
        IS_LEADER=$(echo "$CLUSTER_STATUS" | grep -oP '"is_leader"\s*:\s*\K(true|false)' 2>/dev/null || echo "unknown")
        
        if [ "$IS_LEADER" = "true" ]; then
            echo -e "  Rol Raft:     ${GREEN}LEADER${NC} ★"
        else
            echo -e "  Rol Raft:     ${CYAN}$RAFT_ROLE${NC}"
        fi
    else
        echo -e "  API Health:   ${YELLOW}No responde${NC}"
    fi
    echo ""
done

# ============================================================================
# 5. Verificar infraestructura
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Infraestructura${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

check_infra_service() {
    local service=$1
    local port=$2
    
    echo -n "  $service: "
    
    if docker service ps "$service" --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
        echo -e "${GREEN}Running${NC}"
        return 0
    else
        echo -e "${RED}No disponible${NC}"
        return 1
    fi
}

check_infra_service "coordinator-redis" 6379
check_infra_service "load-balancer" 80
check_infra_service "coredns" 53 2>/dev/null || true

# ============================================================================
# 6. Test de conectividad del Load Balancer
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Load Balancer${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

echo -n "  HTTP (puerto 80): "
if curl -sf "http://$MANAGER_IP/" --max-time 5 &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}No responde (puede estar configurándose)${NC}"
fi

echo -n "  HTTPS (puerto 443): "
if curl -sfk "https://$MANAGER_IP/" --max-time 5 &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}No responde${NC}"
fi

echo -n "  Health endpoint: "
if curl -sf "http://$MANAGER_IP/health" --max-time 5 &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}No responde${NC}"
fi

# ============================================================================
# 7. Resumen
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Resumen${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

NUM_NODES=$(echo "$DISTRISEARCH_NODES" | wc -w)
RUNNING_NODES=$(for NODE in $DISTRISEARCH_NODES; do
    docker service ps "$NODE" --format "{{.CurrentState}}" 2>/dev/null | grep -c "Running" || echo "0"
done | awk '{s+=$1} END {print s}')

echo -e "  Nodos totales:     $NUM_NODES"
echo -e "  Nodos activos:     $RUNNING_NODES"
echo -e "  Manager IP:        $MANAGER_IP"
echo ""

if [ "$RUNNING_NODES" -eq "$NUM_NODES" ] && [ "$NUM_NODES" -gt 0 ]; then
    echo -e "${GREEN}✓ Cluster HA funcionando correctamente${NC}"
else
    echo -e "${YELLOW}⚠ Algunos nodos no están activos${NC}"
fi

echo ""
echo -e "${CYAN}Accesos:${NC}"
echo "  Load Balancer:  http://$MANAGER_IP"
for NODE in $DISTRISEARCH_NODES; do
    NODE_NUM=$(echo "$NODE" | grep -oE "[0-9]+$")
    HTTP_PORT=$((8080 + NODE_NUM))
    API_PORT=$((8000 + NODE_NUM))
    echo "  $NODE:   Frontend http://$MANAGER_IP:$HTTP_PORT  |  API http://$MANAGER_IP:$API_PORT"
done
echo ""

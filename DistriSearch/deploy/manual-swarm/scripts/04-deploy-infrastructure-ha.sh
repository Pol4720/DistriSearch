#!/bin/bash
# ============================================================================
# 04-deploy-infrastructure-ha.sh - Infraestructura HA con CoreDNS y Redis
# ============================================================================
# ARQUITECTURA HA:
# - CoreDNS: DNS de respaldo para descubrimiento de servicios
# - Redis Cluster: Cache distribuido con alta disponibilidad
# - Todos los nodos pueden ser master o slave (Raft decide)
#
# Ejecutar SOLO en el MANAGER
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Infraestructura HA"
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
log_skip() { echo -e "${CYAN}[SKIP]${NC} $1 (ya existe)"; }

echo ""
echo -e "${CYAN}Arquitectura HA (Alta Disponibilidad):${NC}"
echo "  • Todos los nodos son iguales (imagen unificada)"
echo "  • Raft decide dinámicamente quién es el líder"
echo "  • CoreDNS: Descubrimiento de servicios con fallback"
echo "  • Load Balancer: Balanceo entre nodos disponibles"
echo "  • Cada nodo: MongoDB local + Redis local + Backend + Frontend"
echo ""

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

log_info "Nodo Manager confirmado"

# Obtener información del cluster
MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')
NUM_NODES=$(docker node ls --format "{{.ID}}" | wc -l)
NUM_WORKERS=$(docker node ls --filter "role=worker" --format "{{.ID}}" | wc -l)

log_info "Manager IP: $MANAGER_IP"
log_info "Nodos totales: $NUM_NODES (Workers: $NUM_WORKERS)"

# ============================================================================
# 2. Verificar/Crear red overlay
# ============================================================================
NETWORK_EXISTS=$(docker network ls --filter name=distrisearch-network --filter driver=overlay --format "{{.Name}}" 2>/dev/null)

if [ "$NETWORK_EXISTS" = "distrisearch-network" ]; then
    log_skip "Red distrisearch-network (overlay)"
else
    docker network rm distrisearch-network 2>/dev/null || true
    
    log_info "Creando red overlay..."
    docker network create \
        --driver overlay \
        --attachable \
        --subnet 10.0.10.0/24 \
        distrisearch-network
    log_info "Red overlay creada: 10.0.10.0/24"
fi

# ============================================================================
# 3. Construir imagen CoreDNS si no existe
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

log_info "Verificando imagen CoreDNS..."

if docker image inspect distrisearch/coredns:latest &>/dev/null; then
    log_skip "Imagen distrisearch/coredns:latest"
else
    if [ -f "$PROJECT_ROOT/docker/coredns/Dockerfile" ]; then
        log_info "Construyendo imagen CoreDNS..."
        docker build -t distrisearch/coredns:latest -f "$PROJECT_ROOT/docker/coredns/Dockerfile" "$PROJECT_ROOT/docker/coredns"
    else
        log_warn "No se encontró Dockerfile de CoreDNS, usando imagen oficial"
    fi
fi

# ============================================================================
# 4. Construir imagen Load Balancer si no existe
# ============================================================================
log_info "Verificando imagen Load Balancer..."

if docker image inspect distrisearch/load-balancer:latest &>/dev/null; then
    log_skip "Imagen distrisearch/load-balancer:latest"
else
    if [ -f "$PROJECT_ROOT/docker/load-balancer/Dockerfile" ]; then
        log_info "Construyendo imagen Load Balancer..."
        docker build -t distrisearch/load-balancer:latest -f "$PROJECT_ROOT/docker/load-balancer/Dockerfile" "$PROJECT_ROOT/docker/load-balancer"
    else
        log_error "No se encontró Dockerfile del Load Balancer"
        exit 1
    fi
fi

# ============================================================================
# 5. Desplegar CoreDNS (servicio de descubrimiento de respaldo)
# ============================================================================
if docker service inspect coredns &>/dev/null; then
    log_skip "Servicio coredns"
else
    log_info "Desplegando CoreDNS (DNS de respaldo en puerto 5353)..."
    
    docker service create \
        --name coredns \
        --network distrisearch-network \
        --replicas 1 \
        --constraint 'node.role==manager' \
        --publish published=5353,target=5353,protocol=udp \
        --publish published=5353,target=5353,protocol=tcp \
        --health-cmd "dig @localhost -p 5353 distrisearch.local +short || exit 1" \
        --health-interval 30s \
        --health-timeout 10s \
        --health-retries 3 \
        distrisearch/coredns:latest 2>/dev/null || \
    docker service create \
        --name coredns \
        --network distrisearch-network \
        --replicas 1 \
        --constraint 'node.role==manager' \
        --publish published=5353,target=5353,protocol=udp \
        coredns/coredns:1.11.1
    
    log_info "CoreDNS desplegado en puerto 5353"
fi

# ============================================================================
# 6. Desplegar Redis Coordinador (para sesiones y cache global)
# ============================================================================
if docker service inspect coordinator-redis &>/dev/null; then
    log_skip "Servicio coordinator-redis"
else
    log_info "Desplegando Redis Coordinador..."
    
    docker volume create coordinator-redis-data 2>/dev/null || true
    
    docker service create \
        --name coordinator-redis \
        --network distrisearch-network \
        --mount type=volume,source=coordinator-redis-data,target=/data \
        --replicas 1 \
        --constraint 'node.role==manager' \
        --publish published=6379,target=6379 \
        redis:7-alpine redis-server --appendonly yes
    
    log_info "Redis Coordinador desplegado"
fi

# ============================================================================
# 7. Desplegar Load Balancer (en todos los managers)
# ============================================================================
if docker service inspect load-balancer &>/dev/null; then
    log_skip "Servicio load-balancer"
else
    log_info "Desplegando Load Balancer en modo HA..."
    
    docker service create \
        --name load-balancer \
        --network distrisearch-network \
        --mode global \
        --constraint 'node.role==manager' \
        --env HA_MODE=true \
        --env NODE_SERVICE=tasks.node \
        --env NODE_PORT=8000 \
        --env UPDATE_INTERVAL=15 \
        --publish published=80,target=80,mode=ingress \
        --publish published=443,target=443,mode=ingress \
        --health-cmd "curl -f http://localhost/health || exit 1" \
        --health-interval 30s \
        --health-timeout 10s \
        --health-retries 3 \
        distrisearch/load-balancer:latest
    
    log_info "Load Balancer desplegado en modo HA"
fi

# ============================================================================
# 8. Esperar a que los servicios estén listos
# ============================================================================
log_info "Esperando a que los servicios de infraestructura estén listos..."

wait_for_service() {
    local service=$1
    local max_wait=60
    local wait_time=0
    
    echo -n "  $service: "
    while [ $wait_time -lt $max_wait ]; do
        if docker service ps "$service" --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
            echo -e "${GREEN}OK${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        wait_time=$((wait_time + 2))
    done
    echo -e "${YELLOW}PENDIENTE${NC}"
    return 1
}

wait_for_service "coordinator-redis"
wait_for_service "load-balancer"
wait_for_service "coredns" 2>/dev/null || true

# ============================================================================
# 9. Verificar estado
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Infraestructura HA Desplegada${NC}"
echo "=============================================="
echo ""
log_info "Estado de los servicios:"
docker service ls --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}" | grep -E "coredns|redis|load-balancer|NAME"
echo ""

echo -e "${BLUE}Arquitectura HA:${NC}"
echo ""
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │                    LOAD BALANCER                        │"
echo "  │              (Nginx - Puerto 80/443)                    │"
echo "  │     Balancea tráfico entre nodos disponibles            │"
echo "  └─────────────────────────────────────────────────────────┘"
echo "                            │"
echo "           ┌────────────────┼────────────────┐"
echo "           ▼                ▼                ▼"
echo "  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐"
echo "  │   NODO 1    │  │   NODO 2    │  │   NODO N    │"
echo "  │  (Manager)  │  │  (Worker)   │  │  (Worker)   │"
echo "  │             │  │             │  │             │"
echo "  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │"
echo "  │ │ Backend │ │  │ │ Backend │ │  │ │ Backend │ │"
echo "  │ │+Frontend│ │  │ │+Frontend│ │  │ │+Frontend│ │"
echo "  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │"
echo "  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │"
echo "  │ │ MongoDB │ │  │ │ MongoDB │ │  │ │ MongoDB │ │"
echo "  │ │ + Redis │ │  │ │ + Redis │ │  │ │ + Redis │ │"
echo "  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │"
echo "  └─────────────┘  └─────────────┘  └─────────────┘"
echo "         │                │                │"
echo "         └────────────────┼────────────────┘"
echo "                          ▼"
echo "                  ┌───────────────┐"
echo "                  │     RAFT      │"
echo "                  │  (Consenso)   │"
echo "                  │ Elige Líder   │"
echo "                  └───────────────┘"
echo ""
echo -e "${CYAN}Servicios de Coordinación:${NC}"
echo "  • CoreDNS:           DNS de respaldo (puerto 53)"
echo "  • Coordinator Redis: Cache de sesiones global (puerto 6379)"
echo "  • Load Balancer:     Punto de entrada único (puertos 80/443)"
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar ./05-deploy-nodes-ha.sh para desplegar nodos"
echo ""

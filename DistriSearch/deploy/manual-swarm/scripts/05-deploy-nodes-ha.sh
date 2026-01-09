#!/bin/bash
# ============================================================================
# 05-deploy-nodes-ha.sh - Despliega nodos HA con capacidad dual (master/slave)
# ============================================================================
# ARQUITECTURA HA:
# - Todos los nodos usan la MISMA imagen (slave con capacidad dual)
# - El algoritmo Raft decide dinámicamente quién es el líder
# - Cada nodo tiene su propio MongoDB y Redis LOCAL
# - Si el líder cae, Raft elige un nuevo líder automáticamente
#
# Ejecutar en el MANAGER
# Uso: ./05-deploy-nodes-ha.sh [NUM_NODOS] [--clean] [--rebuild]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Desplegar Nodos HA"
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
log_skip() { echo -e "${CYAN}[SKIP]${NC} $1"; }

# ============================================================================
# Parsear argumentos
# ============================================================================
CLEAN_FIRST=false
FORCE_REBUILD=false
NUM_NODES=""
IMAGE_NAME="distrisearch/slave:latest"

for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN_FIRST=true
            ;;
        --rebuild)
            FORCE_REBUILD=true
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                NUM_NODES=$arg
            fi
            ;;
    esac
done

echo ""
echo -e "${CYAN}Arquitectura HA:${NC}"
echo "  • Todos los nodos son IGUALES (imagen unificada)"
echo "  • Raft decide dinámicamente quién es LEADER"
echo "  • Sin master fijo: cualquier nodo puede ser líder"
echo "  • Tolerante a fallos: si el líder cae, se elige otro"
echo ""

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi
log_info "Ejecutando en nodo Manager"

# ============================================================================
# 2. Limpiar servicios existentes si se solicita
# ============================================================================
if [ "$CLEAN_FIRST" = true ]; then
    log_warn "Limpiando todos los servicios de nodos existentes..."
    docker service ls --format "{{.Name}}" | grep -E "^node[0-9]|^distrisearch-node|^distrisearch-slave|^distrisearch-master|^slave[0-9]" | while read svc; do
        docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc"
    done
    sleep 5
fi

# ============================================================================
# 3. Obtener lista de nodos disponibles
# ============================================================================
log_info "Obteniendo lista de nodos..."

# Obtener todos los nodos activos
mapfile -t ALL_NODES < <(docker node ls --format "{{.Hostname}} {{.Status}}" | grep "Ready" | awk '{print $1}' | sort -u)
MANAGER_HOSTNAME=$(docker node ls --filter "role=manager" --format "{{.Hostname}}" | head -1)

TOTAL_NODES=${#ALL_NODES[@]}

if [ "$TOTAL_NODES" -eq 0 ]; then
    log_error "No hay nodos disponibles en el cluster"
    exit 1
fi

# Si no se especificó número de nodos, usar todos los disponibles
NUM_NODES=${NUM_NODES:-$TOTAL_NODES}

# No desplegar más nodos que los disponibles
if [ "$NUM_NODES" -gt "$TOTAL_NODES" ]; then
    log_warn "Ajustando número de nodos de $NUM_NODES a $TOTAL_NODES (nodos disponibles)"
    NUM_NODES=$TOTAL_NODES
fi

log_info "Nodos disponibles: ${ALL_NODES[*]}"
log_info "Desplegando $NUM_NODES nodo(s) HA"

# ============================================================================
# 4. Verificar infraestructura
# ============================================================================
log_info "Verificando servicios de infraestructura..."

check_service() {
    if docker service ps "$1" --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
        echo -e "  $1: ${GREEN}OK${NC}"
        return 0
    else
        echo -e "  $1: ${RED}NO ENCONTRADO${NC}"
        return 1
    fi
}

INFRA_OK=true
check_service "coordinator-redis" || INFRA_OK=false
check_service "load-balancer" || INFRA_OK=false

if [ "$INFRA_OK" != "true" ]; then
    log_error "Falta infraestructura. Ejecuta primero: ./04-deploy-infrastructure-ha.sh"
    exit 1
fi

# ============================================================================
# 5. Verificar/Construir imagen
# ============================================================================
log_info "Verificando imagen: $IMAGE_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

build_image() {
    local DOCKERFILE=""
    if [ -f "$PROJECT_ROOT/docker/slave/Dockerfile" ]; then
        DOCKERFILE="$PROJECT_ROOT/docker/slave/Dockerfile"
        BUILD_CONTEXT="$PROJECT_ROOT"
    else
        log_error "No se encontró el Dockerfile del nodo"
        exit 1
    fi
    
    log_info "Construyendo imagen desde $BUILD_CONTEXT..."
    docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$BUILD_CONTEXT"
}

if [ "$FORCE_REBUILD" = true ]; then
    log_info "Forzando reconstrucción de imagen..."
    build_image
elif ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    log_warn "Imagen no encontrada. Construyendo..."
    build_image
else
    log_info "Imagen encontrada localmente"
fi

# ============================================================================
# 6. Función para crear servicio de forma segura
# ============================================================================
create_service_safe() {
    local SERVICE_NAME=$1
    shift
    local SERVICE_ARGS=("$@")
    
    # Verificar si ya existe
    if docker service inspect "$SERVICE_NAME" &>/dev/null; then
        local STATE=$(docker service ps "$SERVICE_NAME" --format "{{.CurrentState}}" 2>/dev/null | head -1)
        if echo "$STATE" | grep -q "Running"; then
            log_skip "$SERVICE_NAME ya está corriendo"
            return 0
        else
            log_warn "$SERVICE_NAME existe pero no está running, eliminando..."
            docker service rm "$SERVICE_NAME" 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # Crear el servicio
    log_info "Creando $SERVICE_NAME..."
    if docker service create "${SERVICE_ARGS[@]}"; then
        local TRIES=0
        while [ $TRIES -lt 20 ]; do
            sleep 3
            local STATE=$(docker service ps "$SERVICE_NAME" --format "{{.CurrentState}}" 2>/dev/null | head -1)
            if echo "$STATE" | grep -q "Running"; then
                echo -e "  ${GREEN}✓${NC} $SERVICE_NAME iniciado"
                return 0
            elif echo "$STATE" | grep -q "Failed\|Rejected"; then
                log_error "$SERVICE_NAME falló al iniciar"
                docker service ps "$SERVICE_NAME" --no-trunc 2>/dev/null | tail -3
                return 1
            fi
            TRIES=$((TRIES + 1))
        done
        log_warn "$SERVICE_NAME tardando en iniciar, continuando..."
        return 0
    else
        log_error "Error creando $SERVICE_NAME"
        return 1
    fi
}

# ============================================================================
# 7. Generar lista de peers para Raft
# ============================================================================
generate_peer_list() {
    local peers=""
    for i in $(seq 1 $NUM_NODES); do
        if [ -n "$peers" ]; then
            peers="${peers},"
        fi
        peers="${peers}distrisearch-node-${i}:8000"
    done
    echo "$peers"
}

RAFT_PEERS=$(generate_peer_list)
log_info "Peers Raft: $RAFT_PEERS"

# ============================================================================
# 8. Desplegar nodos HA
# ============================================================================
log_info "Desplegando $NUM_NODES nodo(s) HA..."
echo ""

DEPLOYED=0
for i in $(seq 1 $NUM_NODES); do
    NODE_HOSTNAME="${ALL_NODES[$((i-1))]}"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Nodo $i en $NODE_HOSTNAME${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL para este nodo
    # -------------------------------------------------------------------
    create_service_safe "node${i}-mongodb" \
        --name "node${i}-mongodb" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$NODE_HOSTNAME" \
        --mount type=volume,source="node${i}-mongo-data",target=/data/db \
        mongo:4.4 \
        mongod --bind_ip_all
    
    # -------------------------------------------------------------------
    # Redis LOCAL para este nodo
    # -------------------------------------------------------------------
    create_service_safe "node${i}-redis" \
        --name "node${i}-redis" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$NODE_HOSTNAME" \
        --mount type=volume,source="node${i}-redis-data",target=/data \
        redis:7-alpine
    
    # Esperar un momento para que MongoDB y Redis estén listos
    sleep 3
    
    # -------------------------------------------------------------------
    # Nodo DistriSearch (Backend + Frontend + Raft)
    # -------------------------------------------------------------------
    # Puertos: 
    #   - HTTP Frontend: 8080 + i (8081, 8082, ...)
    #   - HTTPS Frontend: 4430 + i (4431, 4432, ...)
    #   - API Backend: 8000 + i (8001, 8002, ...)
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    
    # Determinar si es el primer nodo (candidato inicial a líder)
    IS_INITIAL_LEADER="false"
    if [ $i -eq 1 ]; then
        IS_INITIAL_LEADER="true"
    fi
    
    create_service_safe "distrisearch-node-$i" \
        --name "distrisearch-node-$i" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$NODE_HOSTNAME" \
        --publish published=$HTTP_PORT,target=80 \
        --publish published=$HTTPS_PORT,target=443 \
        --publish published=$API_PORT,target=8000 \
        --env NODE_ID="node-$i" \
        --env NODE_ROLE=slave \
        --env NODE_TYPE=slave \
        --env CLUSTER_ID=distrisearch-cluster \
        --env LOCAL_MONGODB_URI="mongodb://node${i}-mongodb:27017" \
        --env MONGODB_URI="mongodb://node${i}-mongodb:27017/distrisearch_node${i}" \
        --env MONGODB_DATABASE="distrisearch_node${i}" \
        --env LOCAL_REDIS_URL="redis://node${i}-redis:6379" \
        --env REDIS_URL="redis://coordinator-redis:6379" \
        --env COORDINATOR_REDIS_URL="redis://coordinator-redis:6379" \
        --env API_PORT=8000 \
        --env NODE_ADDRESS="distrisearch-node-$i" \
        --env RAFT_ENABLED=true \
        --env RAFT_PEERS="$RAFT_PEERS" \
        --env RAFT_ELECTION_TIMEOUT_MIN=3000 \
        --env RAFT_ELECTION_TIMEOUT_MAX=6000 \
        --env RAFT_HEARTBEAT_INTERVAL=1000 \
        --env CLUSTER_SIZE=$NUM_NODES \
        --env REPLICATION_FACTOR=2 \
        --env LOG_LEVEL=INFO \
        --env IS_INITIAL_CANDIDATE="$IS_INITIAL_LEADER" \
        --mount type=volume,source="node${i}-sqlite",target=/app/data/sqlite \
        --mount type=volume,source="node${i}-raft",target=/app/data/raft \
        --mount type=volume,source="node${i}-docs",target=/app/data/documents \
        --health-cmd "curl -sf http://localhost:8000/api/v1/health/live || curl -sf http://localhost/health || exit 1" \
        --health-interval 30s \
        --health-timeout 15s \
        --health-retries 5 \
        --health-start-period 90s \
        "$IMAGE_NAME"
    
    echo -e "  ${CYAN}Puertos:${NC} HTTP=$HTTP_PORT, HTTPS=$HTTPS_PORT, API=$API_PORT"
    echo -e "  ${CYAN}MongoDB:${NC} node${i}-mongodb:27017"
    echo -e "  ${CYAN}Redis:${NC} node${i}-redis:6379"
    echo ""
    
    DEPLOYED=$((DEPLOYED + 1))
done

# ============================================================================
# 9. Esperar estabilización y verificar estado
# ============================================================================
echo ""
log_info "Esperando a que los nodos se estabilicen y Raft elija líder..."
sleep 15

echo ""
echo -e "${GREEN}Estado de servicios:${NC}"
docker service ls --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}" | grep -E "node|distrisearch|NAME"

# ============================================================================
# 10. Resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Despliegue HA Completado${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}Nodos desplegados: $DEPLOYED${NC}"
echo ""

MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

echo -e "${CYAN}Acceso a los nodos:${NC}"
for i in $(seq 1 $DEPLOYED); do
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    echo "  Nodo-$i:"
    echo "    Frontend: http://$MANAGER_IP:$HTTP_PORT | https://$MANAGER_IP:$HTTPS_PORT"
    echo "    API:      http://$MANAGER_IP:$API_PORT/api/v1"
    echo "    Health:   http://$MANAGER_IP:$API_PORT/api/v1/health"
done

echo ""
echo -e "${CYAN}Load Balancer (punto de entrada único):${NC}"
echo "  Frontend: http://$MANAGER_IP (puerto 80)"
echo "  Frontend: https://$MANAGER_IP (puerto 443)"
echo ""

echo -e "${CYAN}Arquitectura Raft:${NC}"
echo "  • Todos los nodos participan en elección de líder"
echo "  • El líder coordina el cluster y mantiene el VP-Tree global"
echo "  • Los seguidores procesan búsquedas y almacenan documentos"
echo "  • Si el líder cae, se elige automáticamente un nuevo líder"
echo ""

echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  Ver logs nodo 1:    docker service logs -f distrisearch-node-1"
echo "  Ver estado:         docker service ps distrisearch-node-1"
echo "  Ver líder Raft:     curl http://$MANAGER_IP:8001/api/v1/cluster/status"
echo "  Verificar cluster:  ./06-verify-ha-cluster.sh"
echo "  Probar failover:    ./07-test-failover.sh"
echo ""

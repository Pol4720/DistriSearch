#!/bin/bash
# ============================================================================
# 05-deploy-nodes-ha.sh - Despliega nodos HA con TOLERANCIA A PARTICIONES
# ============================================================================
# ARQUITECTURA HA CON TOLERANCIA A PARTICIONES:
# - Cada HOST tiene su propio stack completo (MongoDB + Redis + DistriSearch)
# - Si hay partición de red, cada máquina puede funcionar independientemente
# - El algoritmo BULLY elige el líder entre los nodos que se pueden comunicar
# - Cuando se restaura la conectividad, el cluster se reconecta automáticamente
#
# IMPORTANTE: Para tolerancia a particiones real, el sistema se despliega así:
# - Host A: node-1 (MongoDB-1, Redis-1, DistriSearch-1)
# - Host B: node-2 (MongoDB-2, Redis-2, DistriSearch-2)  
# - Host C: node-3 (MongoDB-3, Redis-3, DistriSearch-3)
# - Load Balancer: GLOBAL (una instancia en cada host)
#
# Cuando Host A se desconecta de la red:
# - Host A sigue funcionando con su stack local
# - Host B y C siguen funcionando con sus stacks
# - Cada partición tiene su propio líder Bully
#
# Ejecutar en el MANAGER
# Uso: ./05-deploy-nodes-ha.sh [NUM_NODOS] [--clean] [--rebuild] [--local]
#
# Opciones:
#   NUM_NODOS   Número de nodos a desplegar (default: número de hosts en swarm)
#   --clean     Limpiar servicios existentes antes de desplegar
#   --rebuild   Forzar reconstrucción de la imagen
#   --local     Desplegar todos los nodos en la máquina local (para pruebas)
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Desplegar Nodos HA"
echo "  (Tolerancia a Particiones)"
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
LOCAL_MODE=false
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
        --local)
            LOCAL_MODE=true
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                NUM_NODES=$arg
            fi
            ;;
    esac
done

echo ""
echo -e "${CYAN}Arquitectura HA con Tolerancia a Particiones:${NC}"
echo "  • Cada HOST tiene un stack completo (MongoDB + Redis + DistriSearch)"
echo "  • BULLY decide dinámicamente quién es LEADER (mayor ID gana)"
echo "  • Si hay partición de red, cada host funciona independientemente"
echo "  • Load Balancer en modo GLOBAL: una instancia por host"
if [ "$LOCAL_MODE" = true ]; then
    echo ""
    echo -e "${YELLOW}  MODO LOCAL: Todos los nodos se despliegan en esta máquina${NC}"
    echo -e "${YELLOW}  (No hay tolerancia a particiones real en este modo)${NC}"
fi
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
# 3. Obtener lista de hosts disponibles
# ============================================================================
log_info "Obteniendo lista de hosts..."

# Obtener todos los nodos activos con su hostname
mapfile -t ALL_HOSTS < <(docker node ls --format "{{.Hostname}} {{.Status}}" | grep "Ready" | awk '{print $1}' | sort -u)
LOCAL_HOSTNAME=$(hostname)

TOTAL_HOSTS=${#ALL_HOSTS[@]}

if [ "$TOTAL_HOSTS" -eq 0 ]; then
    log_error "No hay nodos disponibles en el cluster"
    exit 1
fi

log_info "Hosts disponibles: ${ALL_HOSTS[*]}"

# En modo local, podemos desplegar múltiples nodos en la misma máquina
if [ "$LOCAL_MODE" = true ]; then
    NUM_NODES=${NUM_NODES:-3}
    log_info "Modo LOCAL: Desplegando $NUM_NODES nodo(s) en $LOCAL_HOSTNAME"
else
    # En modo distribuido con tolerancia a particiones:
    # Desplegamos 1 nodo POR HOST para que cada host tenga stack completo
    NUM_NODES=${NUM_NODES:-$TOTAL_HOSTS}
    
    if [ "$NUM_NODES" -gt "$TOTAL_HOSTS" ]; then
        log_warn "Solo hay $TOTAL_HOSTS host(s). Cada host tendrá 1 nodo."
        log_warn "Para múltiples nodos en un host, usa --local"
        NUM_NODES=$TOTAL_HOSTS
    fi
    
    log_info "Modo DISTRIBUIDO: 1 nodo por host para tolerancia a particiones"
fi

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
# 7. Generar lista de peers para elección Bully
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

BULLY_PEERS=$(generate_peer_list)
log_info "Peers Bully: $BULLY_PEERS"

# JWT_SECRET compartido
JWT_SECRET="${JWT_SECRET:-distrisearch-cluster-shared-jwt-secret-$(date +%Y%m%d)}"
log_info "JWT Secret compartido configurado"

# ============================================================================
# 8. Desplegar nodos HA con tolerancia a particiones
# ============================================================================
log_info "Desplegando $NUM_NODES nodo(s) HA..."
echo ""

DEPLOYED=0
for i in $(seq 1 $NUM_NODES); do
    # -----------------------------------------------------------------------
    # Determinar en qué host desplegar
    # En modo distribuido: cada host tiene exactamente 1 nodo
    # En modo local: todos los nodos en el mismo host
    # -----------------------------------------------------------------------
    if [ "$LOCAL_MODE" = true ]; then
        NODE_HOSTNAME="$LOCAL_HOSTNAME"
    else
        HOST_INDEX=$(( (i - 1) % TOTAL_HOSTS ))
        NODE_HOSTNAME="${ALL_HOSTS[$HOST_INDEX]}"
    fi
    
    CONSTRAINT_ARGS=(--constraint "node.hostname==$NODE_HOSTNAME")
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Nodo $i en $NODE_HOSTNAME${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL para este nodo (FIJADO al host)
    # -------------------------------------------------------------------
    create_service_safe "node${i}-mongodb" \
        --name "node${i}-mongodb" \
        --network distrisearch-network \
        --replicas 1 \
        "${CONSTRAINT_ARGS[@]}" \
        --mount type=volume,source="node${i}-mongo-data",target=/data/db \
        mongo:4.4 \
        mongod --bind_ip_all
    
    # -------------------------------------------------------------------
    # Redis LOCAL para este nodo (FIJADO al host)
    # -------------------------------------------------------------------
    create_service_safe "node${i}-redis" \
        --name "node${i}-redis" \
        --network distrisearch-network \
        --replicas 1 \
        "${CONSTRAINT_ARGS[@]}" \
        --mount type=volume,source="node${i}-redis-data",target=/data \
        redis:7-alpine
    
    sleep 3
    
    # -------------------------------------------------------------------
    # Nodo DistriSearch (FIJADO al host)
    # Puertos publicados globalmente para que el LB pueda alcanzarlos
    # -------------------------------------------------------------------
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    
    create_service_safe "distrisearch-node-$i" \
        --name "distrisearch-node-$i" \
        --network name=distrisearch-network,alias=distrisearch-node \
        --replicas 1 \
        "${CONSTRAINT_ARGS[@]}" \
        --publish published=$HTTP_PORT,target=80,mode=host \
        --publish published=$HTTPS_PORT,target=443,mode=host \
        --publish published=$API_PORT,target=8000,mode=host \
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
        --env BULLY_ENABLED=true \
        --env BULLY_PEERS="$BULLY_PEERS" \
        --env BULLY_ELECTION_TIMEOUT=5000 \
        --env BULLY_HEARTBEAT_INTERVAL=2000 \
        --env CLUSTER_SIZE=$NUM_NODES \
        --env REPLICATION_FACTOR=2 \
        --env LOG_LEVEL=INFO \
        --env JWT_SECRET="$JWT_SECRET" \
        --mount type=volume,source="node${i}-sqlite",target=/app/data/sqlite \
        --mount type=volume,source="node${i}-data",target=/app/data \
        --mount type=volume,source="node${i}-docs",target=/app/data/documents \
        --health-cmd "curl -sf http://localhost:8000/api/v1/health/live || curl -sf http://localhost/health || exit 1" \
        --health-interval 30s \
        --health-timeout 15s \
        --health-retries 5 \
        --health-start-period 90s \
        "$IMAGE_NAME"
    
    echo -e "  ${CYAN}Host:${NC} $NODE_HOSTNAME (stack completo fijado aquí)"
    echo -e "  ${CYAN}Puertos:${NC} HTTP=$HTTP_PORT, HTTPS=$HTTPS_PORT, API=$API_PORT"
    echo -e "  ${CYAN}MongoDB:${NC} node${i}-mongodb:27017"
    echo -e "  ${CYAN}Redis:${NC} node${i}-redis:6379"
    echo ""
    
    DEPLOYED=$((DEPLOYED + 1))
done

# ============================================================================
# 9. Esperar estabilización
# ============================================================================
echo ""
log_info "Esperando a que los nodos se estabilicen y Bully elija líder..."
sleep 15

echo ""
echo -e "${GREEN}Estado de servicios:${NC}"
docker service ls --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}" | grep -E "node|distrisearch|NAME"

# ============================================================================
# 10. Mostrar distribución de servicios por host
# ============================================================================
echo ""
echo -e "${CYAN}Distribución de servicios por HOST:${NC}"
echo -e "${CYAN}(Para tolerancia a particiones, cada host debe tener su stack completo)${NC}"
echo ""

for HOST in "${ALL_HOSTS[@]}"; do
    echo -e "${BLUE}Host: $HOST${NC}"
    docker service ls --format "{{.Name}}" | while read svc; do
        NODE_HOST=$(docker service ps "$svc" --format "{{.Node}}" 2>/dev/null | head -1)
        if [ "$NODE_HOST" = "$HOST" ]; then
            echo "  - $svc"
        fi
    done
    echo ""
done

# ============================================================================
# 11. Resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Despliegue HA Completado${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}Nodos desplegados: $DEPLOYED${NC}"
if [ "$LOCAL_MODE" = true ]; then
    echo -e "${YELLOW}Modo: LOCAL (todos en $LOCAL_HOSTNAME)${NC}"
else
    echo -e "${GREEN}Modo: DISTRIBUIDO con Tolerancia a Particiones${NC}"
fi
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

echo -e "${CYAN}Algoritmo de Consenso - BULLY:${NC}"
echo "  • El nodo con mayor ID (node-$NUM_NODES) será el líder inicial"
echo "  • El líder coordina el cluster y federa las búsquedas"
echo "  • Si el líder cae, el siguiente nodo activo con mayor ID toma el liderazgo"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  TOLERANCIA A PARTICIONES${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Cada host tiene su stack completo (MongoDB + Redis + DistriSearch)."
echo "  Si hay partición de red:"
echo ""
echo "  1. Cada host puede funcionar independientemente"
echo "  2. El Load Balancer local enruta al nodo local disponible"
echo "  3. Bully elige líder en cada partición"
echo "  4. Cuando se restaura la conectividad, el cluster se reconecta"
echo ""
echo "  Para probar: Desconecta un host de la red y verifica que"
echo "  sigue funcionando accediendo a su IP directamente."
echo ""

echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  Ver logs nodo 1:    docker service logs -f distrisearch-node-1"
echo "  Ver estado:         docker service ps distrisearch-node-1"
echo "  Ver líder Bully:    curl http://$MANAGER_IP:8001/api/v1/cluster/status"
echo "  Verificar cluster:  ./06-verify-ha-cluster.sh"
echo "  Probar failover:    ./07-test-failover.sh"
echo ""

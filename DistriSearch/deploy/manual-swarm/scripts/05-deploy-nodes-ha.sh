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
# USO BÁSICO:
#   ./05-deploy-nodes-ha.sh [NUM_NODOS] [OPCIONES]
#
# OPCIONES:
#   NUM_NODOS                   Número total de nodos (default: auto-detectar)
#   --clean                     Limpiar TODOS los servicios existentes antes de desplegar
#   --rebuild                   Forzar reconstrucción de la imagen Docker
#   --local                     Desplegar todos los nodos en la máquina local
#   --host HOSTNAME             Desplegar solo en un host específico
#   --hosts HOST1,HOST2,...     Desplegar solo en hosts específicos
#   --start-id N                ID inicial para los nuevos nodos (default: siguiente disponible)
#   --count N                   Cuántos nodos nuevos crear
#   --add-to-host HOSTNAME N    Añadir N nodos al host específico sin tocar existentes
#   --image IMAGE_NAME          Usar una imagen Docker específica
#   --dry-run                   Mostrar qué se haría sin ejecutar
#   --status                    Mostrar estado actual de nodos desplegados
#   --help, -h                  Mostrar esta ayuda extendida
#
# EJEMPLOS:
#
#   # [DESARROLLO] Desplegar 3 nodos localmente
#   ./05-deploy-nodes-ha.sh 3 --local --rebuild
#
#   # [NUEVA MÁQUINA] Una máquina se unió al swarm, añadir 2 nodos en ella
#   ./05-deploy-nodes-ha.sh --add-to-host nuevo-hostname 2
#
#   # [ESCALAR] Ya existen nodos 1-3, crear nodos 4 y 5 en hosts específicos
#   ./05-deploy-nodes-ha.sh --start-id 4 --count 2 --hosts worker-1,worker-2
#
#   # [DISTRIBUIDO] Desplegar 1 nodo por host del swarm
#   ./05-deploy-nodes-ha.sh
#
#   # [REDISTRIBUIR] Limpiar todo y redesplegar 5 nodos
#   ./05-deploy-nodes-ha.sh 5 --clean --rebuild
#
#   # [VER ESTADO] Ver nodos actualmente desplegados
#   ./05-deploy-nodes-ha.sh --status
#
#   # [SIMULAR] Ver qué se haría sin ejecutar
#   ./05-deploy-nodes-ha.sh --add-to-host worker-2 3 --dry-run
#
# FLUJO TÍPICO PARA AÑADIR MÁQUINAS:
#
#   1. En la nueva máquina:
#      docker swarm join --token TOKEN MANAGER_IP:2377
#
#   2. En el manager, ver hosts disponibles:
#      ./05-deploy-nodes-ha.sh --status
#
#   3. Añadir nodos a la nueva máquina:
#      ./05-deploy-nodes-ha.sh --add-to-host nuevo-hostname 2
#
# ============================================================================

set -e

show_help() {
    head -62 "$0" | tail -58
    exit 0
}

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
log_dry() { echo -e "${BLUE}[DRY-RUN]${NC} $1"; }

# ============================================================================
# Valores por defecto
# ============================================================================
CLEAN_FIRST=false
FORCE_REBUILD=false
LOCAL_MODE=false
DRY_RUN=false
SHOW_STATUS=false
NUM_NODES=""
START_ID=""
NODE_COUNT=""
TARGET_HOST=""
TARGET_HOSTS=""
ADD_TO_HOST=""
ADD_COUNT=""
IMAGE_NAME="distrisearch/slave:latest"

# ============================================================================
# Parsear argumentos
# ============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_FIRST=true
            shift
            ;;
        --rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --local)
            LOCAL_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --host)
            TARGET_HOST="$2"
            shift 2
            ;;
        --hosts)
            TARGET_HOSTS="$2"
            shift 2
            ;;
        --start-id)
            START_ID="$2"
            shift 2
            ;;
        --count)
            NODE_COUNT="$2"
            shift 2
            ;;
        --add-to-host)
            ADD_TO_HOST="$2"
            ADD_COUNT="$3"
            if ! [[ "$ADD_COUNT" =~ ^[0-9]+$ ]]; then
                log_error "--add-to-host requiere HOSTNAME y CANTIDAD (ej: --add-to-host worker-1 2)"
                exit 1
            fi
            shift 3
            ;;
        --image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            ;;
        *)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                NUM_NODES="$1"
            else
                log_error "Argumento desconocido: $1"
                echo "Usa --help para ver las opciones"
                exit 1
            fi
            shift
            ;;
    esac
done

echo "=============================================="
echo "  DistriSearch - Desplegar Nodos HA"
echo "  (Tolerancia a Particiones)"
echo "=============================================="

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
# 2. Obtener información del cluster
# ============================================================================
log_info "Analizando cluster..."

# Obtener todos los hosts disponibles
mapfile -t ALL_HOSTS < <(docker node ls --format "{{.Hostname}} {{.Status}}" | grep "Ready" | awk '{print $1}' | sort -u)
LOCAL_HOSTNAME=$(hostname)
TOTAL_HOSTS=${#ALL_HOSTS[@]}

# Detectar nodos DistriSearch existentes
get_existing_nodes() {
    docker service ls --format "{{.Name}}" 2>/dev/null | grep -E "^distrisearch-node-[0-9]+$" | sort -V || true
}

get_highest_node_id() {
    local highest=0
    for svc in $(get_existing_nodes); do
        local id=$(echo "$svc" | grep -oE '[0-9]+$')
        if [ "$id" -gt "$highest" ]; then
            highest=$id
        fi
    done
    echo $highest
}

get_node_host() {
    local node_id=$1
    docker service ps "distrisearch-node-$node_id" --format "{{.Node}}" 2>/dev/null | head -1 || echo "desconocido"
}

EXISTING_NODES=$(get_existing_nodes)
if [ -n "$EXISTING_NODES" ]; then
    EXISTING_COUNT=$(echo "$EXISTING_NODES" | wc -l)
else
    EXISTING_COUNT=0
fi
HIGHEST_ID=$(get_highest_node_id)

# ============================================================================
# 3. Mostrar estado si se solicita
# ============================================================================
if [ "$SHOW_STATUS" = true ]; then
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  ESTADO ACTUAL DEL CLUSTER${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}Hosts disponibles en Swarm (${TOTAL_HOSTS}):${NC}"
    for h in "${ALL_HOSTS[@]}"; do
        local_mark=""
        [ "$h" = "$LOCAL_HOSTNAME" ] && local_mark=" (local)"
        echo "  • $h$local_mark"
    done
    echo ""
    
    if [ "$EXISTING_COUNT" -gt 0 ]; then
        echo -e "${GREEN}Nodos DistriSearch desplegados ($EXISTING_COUNT):${NC}"
        for svc in $EXISTING_NODES; do
            local id=$(echo "$svc" | grep -oE '[0-9]+$')
            local host=$(get_node_host "$id")
            local state=$(docker service ps "$svc" --format "{{.CurrentState}}" 2>/dev/null | head -1)
            if echo "$state" | grep -q "Running"; then
                echo -e "  ${GREEN}✓${NC} node-$id en $host (Running)"
            else
                echo -e "  ${RED}✗${NC} node-$id en $host ($state)"
            fi
        done
        echo ""
        echo "  Siguiente ID disponible: $((HIGHEST_ID + 1))"
    else
        echo -e "${YELLOW}No hay nodos DistriSearch desplegados${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}Para añadir nodos:${NC}"
    echo "  ./05-deploy-nodes-ha.sh --add-to-host HOSTNAME CANTIDAD"
    echo "  ./05-deploy-nodes-ha.sh --start-id $((HIGHEST_ID + 1)) --count N --hosts HOST1,HOST2"
    echo ""
    exit 0
fi

# ============================================================================
# 4. Determinar qué nodos desplegar
# ============================================================================
NODES_TO_DEPLOY=()
DEPLOY_HOSTS=()

if [ -n "$ADD_TO_HOST" ]; then
    # Modo: Añadir N nodos a un host específico
    log_info "Modo: Añadir $ADD_COUNT nodo(s) al host '$ADD_TO_HOST'"
    
    # Verificar que el host existe
    if ! printf '%s\n' "${ALL_HOSTS[@]}" | grep -qx "$ADD_TO_HOST"; then
        log_error "Host '$ADD_TO_HOST' no encontrado en el swarm"
        echo "Hosts disponibles: ${ALL_HOSTS[*]}"
        exit 1
    fi
    
    START_ID=${START_ID:-$((HIGHEST_ID + 1))}
    for i in $(seq 0 $((ADD_COUNT - 1))); do
        NODES_TO_DEPLOY+=($((START_ID + i)))
        DEPLOY_HOSTS+=("$ADD_TO_HOST")
    done

elif [ -n "$NODE_COUNT" ]; then
    # Modo: Crear N nodos con IDs consecutivos
    START_ID=${START_ID:-$((HIGHEST_ID + 1))}
    
    # Determinar hosts objetivo
    if [ -n "$TARGET_HOSTS" ]; then
        IFS=',' read -ra SELECTED_HOSTS <<< "$TARGET_HOSTS"
    elif [ -n "$TARGET_HOST" ]; then
        SELECTED_HOSTS=("$TARGET_HOST")
    elif [ "$LOCAL_MODE" = true ]; then
        SELECTED_HOSTS=("$LOCAL_HOSTNAME")
    else
        SELECTED_HOSTS=("${ALL_HOSTS[@]}")
    fi
    
    log_info "Modo: Crear $NODE_COUNT nodo(s) empezando en ID $START_ID"
    
    for i in $(seq 0 $((NODE_COUNT - 1))); do
        NODES_TO_DEPLOY+=($((START_ID + i)))
        host_idx=$((i % ${#SELECTED_HOSTS[@]}))
        DEPLOY_HOSTS+=("${SELECTED_HOSTS[$host_idx]}")
    done

elif [ -n "$NUM_NODES" ]; then
    # Modo: Desplegar N nodos total (puede requerir --clean)
    if [ "$EXISTING_COUNT" -gt 0 ] && [ "$CLEAN_FIRST" != true ]; then
        log_warn "Ya existen $EXISTING_COUNT nodos. Usa --clean para reemplazarlos o --add-to-host/--count para añadir."
        log_info "Estado actual: nodos 1-$HIGHEST_ID desplegados"
        echo ""
        echo "Opciones:"
        echo "  1. Añadir más nodos:  ./05-deploy-nodes-ha.sh --start-id $((HIGHEST_ID + 1)) --count N"
        echo "  2. Reemplazar todo:   ./05-deploy-nodes-ha.sh $NUM_NODES --clean"
        exit 1
    fi
    
    # Determinar hosts objetivo
    if [ "$LOCAL_MODE" = true ]; then
        SELECTED_HOSTS=("$LOCAL_HOSTNAME")
    elif [ -n "$TARGET_HOSTS" ]; then
        IFS=',' read -ra SELECTED_HOSTS <<< "$TARGET_HOSTS"
    elif [ -n "$TARGET_HOST" ]; then
        SELECTED_HOSTS=("$TARGET_HOST")
    else
        SELECTED_HOSTS=("${ALL_HOSTS[@]}")
    fi
    
    log_info "Modo: Desplegar $NUM_NODES nodo(s) total"
    
    for i in $(seq 1 $NUM_NODES); do
        NODES_TO_DEPLOY+=($i)
        host_idx=$(( (i - 1) % ${#SELECTED_HOSTS[@]} ))
        DEPLOY_HOSTS+=("${SELECTED_HOSTS[$host_idx]}")
    done

else
    # Modo por defecto: 1 nodo por host disponible (si no hay existentes)
    if [ "$EXISTING_COUNT" -gt 0 ]; then
        echo ""
        echo -e "${CYAN}Estado actual:${NC} $EXISTING_COUNT nodos desplegados (IDs 1-$HIGHEST_ID)"
        echo ""
        echo "Para ver estado detallado:"
        echo "  ./05-deploy-nodes-ha.sh --status"
        echo ""
        echo "Para añadir más nodos:"
        echo "  ./05-deploy-nodes-ha.sh --add-to-host HOSTNAME CANTIDAD"
        echo "  ./05-deploy-nodes-ha.sh --start-id $((HIGHEST_ID + 1)) --count N"
        echo ""
        exit 0
    fi
    
    if [ "$LOCAL_MODE" = true ]; then
        NUM_NODES=3
        log_info "Modo local sin especificar cantidad: desplegando 3 nodos"
        for i in $(seq 1 $NUM_NODES); do
            NODES_TO_DEPLOY+=($i)
            DEPLOY_HOSTS+=("$LOCAL_HOSTNAME")
        done
    else
        NUM_NODES=$TOTAL_HOSTS
        log_info "Modo distribuido: 1 nodo por host ($TOTAL_HOSTS hosts)"
        for i in $(seq 1 $NUM_NODES); do
            NODES_TO_DEPLOY+=($i)
            DEPLOY_HOSTS+=("${ALL_HOSTS[$((i-1))]}")
        done
    fi
fi

# ============================================================================
# 5. Mostrar plan de despliegue
# ============================================================================
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  PLAN DE DESPLIEGUE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Nodos existentes: $EXISTING_COUNT"
echo "Nodos a desplegar: ${#NODES_TO_DEPLOY[@]}"
echo ""
echo "Distribución:"
for idx in "${!NODES_TO_DEPLOY[@]}"; do
    node_id=${NODES_TO_DEPLOY[$idx]}
    host=${DEPLOY_HOSTS[$idx]}
    echo "  • Nodo $node_id → $host"
done
echo ""

if [ "$DRY_RUN" = true ]; then
    log_dry "Modo simulación - no se ejecutará nada"
    exit 0
fi

# ============================================================================
# 6. Limpiar si se solicita
# ============================================================================
if [ "$CLEAN_FIRST" = true ]; then
    log_warn "Limpiando todos los servicios de nodos existentes..."
    for svc in $(docker service ls --format "{{.Name}}" | grep -E "^node[0-9]|^distrisearch-node" || true); do
        docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc" || true
    done
    sleep 5
fi

# ============================================================================
# 7. Verificar infraestructura
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
# 8. Verificar/Construir imagen
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
# 9. Función para crear servicio de forma segura
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
# 10. Generar lista de peers para elección Bully
# ============================================================================
generate_peer_list() {
    local peers=""
    # Incluir nodos existentes + nuevos
    local max_id=${NODES_TO_DEPLOY[-1]}
    
    # Si hay nodos existentes, considerar el máximo entre existentes y nuevos
    if [ "$HIGHEST_ID" -gt "$max_id" ]; then
        max_id=$HIGHEST_ID
    fi
    
    for i in $(seq 1 $max_id); do
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
# 11. Desplegar nodos HA con tolerancia a particiones
# ============================================================================
log_info "Desplegando ${#NODES_TO_DEPLOY[@]} nodo(s) HA..."
echo ""

DEPLOYED=0
for idx in "${!NODES_TO_DEPLOY[@]}"; do
    i=${NODES_TO_DEPLOY[$idx]}
    NODE_HOSTNAME=${DEPLOY_HOSTS[$idx]}
    
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
    # -------------------------------------------------------------------
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    
    # Calcular CLUSTER_SIZE considerando nodos existentes + nuevos
    TOTAL_CLUSTER_SIZE=$((EXISTING_COUNT + ${#NODES_TO_DEPLOY[@]}))
    if [ "$CLEAN_FIRST" = true ]; then
        TOTAL_CLUSTER_SIZE=${#NODES_TO_DEPLOY[@]}
    fi
    
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
        --env CLUSTER_SIZE=$TOTAL_CLUSTER_SIZE \
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
    
    DEPLOYED=$((DEPLOYED + 1))
    echo ""
done

# ============================================================================
# 12. Resumen final
# ============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  DESPLIEGUE COMPLETADO${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Nodos desplegados en esta ejecución: $DEPLOYED"
echo ""

# Mostrar todos los nodos activos
echo "Estado de todos los nodos DistriSearch:"
for svc in $(docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-[0-9]+$" | sort -V); do
    id=$(echo "$svc" | grep -oE '[0-9]+$')
    host=$(docker service ps "$svc" --format "{{.Node}}" 2>/dev/null | head -1)
    state=$(docker service ps "$svc" --format "{{.CurrentState}}" 2>/dev/null | head -1)
    port=$((8000 + id))
    if echo "$state" | grep -q "Running"; then
        echo -e "  ${GREEN}✓${NC} node-$id en $host → puerto $port"
    else
        echo -e "  ${RED}✗${NC} node-$id en $host ($state)"
    fi
done

echo ""
echo "Próximos pasos:"
echo "  1. Verificar salud: curl http://localhost:PORT/api/v1/health/live"
echo "  2. Ver estado:      ./05-deploy-nodes-ha.sh --status"
echo "  3. Añadir más:      ./05-deploy-nodes-ha.sh --add-to-host HOSTNAME N"
echo ""

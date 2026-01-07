#!/bin/bash
# ============================================================================
# 06-deploy-slave.sh - Despliega nodos Slave (Backend + Frontend integrado)
# ============================================================================
# ARQUITECTURA:
# - Cada slave tiene Backend (FastAPI) + Frontend (React/Nginx) en un container
# - Cada slave tiene su propia instancia de MongoDB y Redis (LOCAL)
# - Frontend accesible en puertos 80/443 (Nginx)
# - Backend API en puerto 8000 (interno, proxy por Nginx)
#
# Ejecutar en el MANAGER para desplegar slaves en los workers
# Uso: ./06-deploy-slave.sh [NUM_REPLICAS] [--update] [--rebuild] [--clean]
#
# Opciones:
#   --update    Forzar actualización de la imagen en servicios existentes
#   --rebuild   Reconstruir imagen antes de desplegar
#   --clean     Eliminar todos los servicios slave antes de desplegar
# ============================================================================

set -e

echo "============================================="
echo "  DistriSearch - Desplegar Slaves"
echo "============================================="

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
FORCE_UPDATE=false
FORCE_REBUILD=false
CLEAN_FIRST=false
NUM_REPLICAS=""
IMAGE_NAME="distrisearch/slave:latest"

for arg in "$@"; do
    case $arg in
        --update)
            FORCE_UPDATE=true
            ;;
        --rebuild)
            FORCE_REBUILD=true
            ;;
        --clean)
            CLEAN_FIRST=true
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                NUM_REPLICAS=$arg
            fi
            ;;
    esac
done

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
    log_warn "Limpiando todos los servicios slave existentes..."
    docker service ls --format "{{.Name}}" | grep -E "^slave[0-9]|^distrisearch-slave" | while read svc; do
        docker service rm "$svc" 2>/dev/null && echo "  Eliminado: $svc"
    done
    sleep 5
fi

# ============================================================================
# 3. Listar workers disponibles
# ============================================================================
log_info "Obteniendo lista de workers..."

# Obtener workers activos (Ready)
mapfile -t WORKERS < <(docker node ls --filter "role=worker" --format "{{.Hostname}} {{.Status}}" | grep "Ready" | awk '{print $1}' | sort -u)
NUM_WORKERS=${#WORKERS[@]}

if [ "$NUM_WORKERS" -eq 0 ]; then
    log_warn "No hay workers disponibles, desplegando en el manager"
    MANAGER_HOSTNAME=$(docker node ls --filter "role=manager" --format "{{.Hostname}}" | head -1)
    WORKERS=("$MANAGER_HOSTNAME")
    NUM_WORKERS=1
fi

# Si no se especificó número de réplicas, usar el número de workers
NUM_REPLICAS=${NUM_REPLICAS:-$NUM_WORKERS}

# No desplegar más slaves que workers disponibles
if [ "$NUM_REPLICAS" -gt "$NUM_WORKERS" ]; then
    log_warn "Ajustando número de réplicas de $NUM_REPLICAS a $NUM_WORKERS (workers disponibles)"
    NUM_REPLICAS=$NUM_WORKERS
fi

log_info "Workers disponibles: ${WORKERS[*]}"
log_info "Desplegando $NUM_REPLICAS slave(s)"

# ============================================================================
# 4. Verificar Master
# ============================================================================
log_info "Verificando que el Master está corriendo..."

MASTER_RUNNING=$(docker service ps distrisearch-master --format "{{.CurrentState}}" 2>/dev/null | grep -c "Running" || echo "0")
if [ "$MASTER_RUNNING" -eq 0 ]; then
    log_error "El Master no está corriendo. Ejecuta primero: ./05-deploy-master.sh"
    exit 1
fi
echo -e "  Master: ${GREEN}OK${NC}"

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
    elif [ -f "/opt/distrisearch/code/docker/slave/Dockerfile" ]; then
        DOCKERFILE="/opt/distrisearch/code/docker/slave/Dockerfile"
        BUILD_CONTEXT="/opt/distrisearch/code"
    fi
    
    if [ -z "$DOCKERFILE" ]; then
        log_error "No se encontró el Dockerfile del slave"
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
        # Esperar a que inicie (máximo 30 segundos)
        local TRIES=0
        while [ $TRIES -lt 15 ]; do
            sleep 2
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
# 7. Desplegar slaves
# ============================================================================
log_info "Desplegando $NUM_REPLICAS slave(s)..."
echo ""

DEPLOYED=0
for i in $(seq 1 $NUM_REPLICAS); do
    WORKER="${WORKERS[$((i-1))]}"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Slave $i en $WORKER${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL
    # -------------------------------------------------------------------
    create_service_safe "slave${i}-mongodb" \
        --name "slave${i}-mongodb" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --mount type=volume,source="slave${i}-mongo-data",target=/data/db \
        mongo:4.4 \
        mongod --bind_ip_all
    
    # -------------------------------------------------------------------
    # Redis LOCAL
    # -------------------------------------------------------------------
    create_service_safe "slave${i}-redis" \
        --name "slave${i}-redis" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --mount type=volume,source="slave${i}-redis-data",target=/data \
        redis:7-alpine
    
    # Esperar un momento para que MongoDB y Redis estén listos
    sleep 3
    
    # -------------------------------------------------------------------
    # Slave Node (Backend + Frontend)
    # -------------------------------------------------------------------
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8001 + i))
    
    create_service_safe "distrisearch-slave-$i" \
        --name "distrisearch-slave-$i" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --publish published=$HTTP_PORT,target=80 \
        --publish published=$HTTPS_PORT,target=443 \
        --publish published=$API_PORT,target=8000 \
        --env NODE_ID="slave-$i" \
        --env NODE_ROLE=slave \
        --env CLUSTER_ID=distrisearch-cluster \
        --env LOCAL_MONGODB_URI="mongodb://slave${i}-mongodb:27017" \
        --env MONGODB_URI="mongodb://slave${i}-mongodb:27017/distrisearch_slave${i}" \
        --env MONGODB_DATABASE="distrisearch_slave${i}" \
        --env REDIS_URL="redis://slave${i}-redis:6379" \
        --env MASTER_HOST=distrisearch-master \
        --env MASTER_PORT=8001 \
        --env API_PORT=8000 \
        --env NODE_ADDRESS="distrisearch-slave-$i" \
        --env REPLICATION_FACTOR=2 \
        --env LOG_LEVEL=INFO \
        --env RAFT_ENABLED=true \
        --mount type=volume,source="slave${i}-sqlite",target=/app/data/sqlite \
        --mount type=volume,source="slave${i}-raft",target=/app/data/raft \
        --mount type=volume,source="slave${i}-docs",target=/app/data/documents \
        --health-cmd "curl -f http://localhost:8000/api/v1/health/live || exit 1" \
        --health-interval 30s \
        --health-timeout 10s \
        --health-retries 3 \
        "$IMAGE_NAME"
    
    echo -e "  ${CYAN}Puertos:${NC} HTTP=$HTTP_PORT, HTTPS=$HTTPS_PORT, API=$API_PORT"
    echo ""
    
    DEPLOYED=$((DEPLOYED + 1))
done

# ============================================================================
# 8. Verificar estado final
# ============================================================================
echo ""
log_info "Esperando a que los servicios se estabilicen..."
sleep 10

echo ""
echo -e "${GREEN}Estado de servicios:${NC}"
docker service ls --format "table {{.Name}}\t{{.Replicas}}\t{{.Image}}" | grep -E "slave|NAME"

# ============================================================================
# 9. Resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Despliegue Completado${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}Slaves desplegados: $DEPLOYED${NC}"
echo ""

MASTER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

for i in $(seq 1 $DEPLOYED); do
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8001 + i))
    echo "Slave-$i:"
    echo "  Frontend: http://<worker-ip>:$HTTP_PORT | https://<worker-ip>:$HTTPS_PORT"
    echo "  API:      http://<worker-ip>:$API_PORT"
done

echo ""
echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  Ver logs:     docker service logs -f distrisearch-slave-1"
echo "  Ver estado:   docker service ps distrisearch-slave-1"
echo "  Actualizar:   ./06-deploy-slave.sh --update"
echo "  Limpiar:      ./06-deploy-slave.sh --clean"
echo ""

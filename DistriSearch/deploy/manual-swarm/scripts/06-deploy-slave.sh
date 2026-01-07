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
# Uso: ./06-deploy-slave.sh [NUM_REPLICAS] [IMAGE_NAME] [--update]
#
# Opciones:
#   --update    Forzar actualización de la imagen en servicios existentes
#   --rebuild   Reconstruir imagen antes de desplegar
# ============================================================================

set -e

echo "============================================="
echo "  DistriSearch - Desplegar Slaves"
echo "============================================="
echo "  Arquitectura: Backend+Frontend + MongoDB/Redis LOCAL por nodo"
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
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1 (ya existe)"; }
log_update() { echo -e "${CYAN}[UPDATE]${NC} $1"; }

# Parsear argumentos
FORCE_UPDATE=false
FORCE_REBUILD=false
NUM_REPLICAS=""
IMAGE_NAME=""

for arg in "$@"; do
    case $arg in
        --update)
            FORCE_UPDATE=true
            ;;
        --rebuild)
            FORCE_REBUILD=true
            ;;
        *)
            if [ -z "$NUM_REPLICAS" ] && [[ "$arg" =~ ^[0-9]+$ ]]; then
                NUM_REPLICAS=$arg
            elif [ -z "$IMAGE_NAME" ]; then
                IMAGE_NAME=$arg
            fi
            ;;
    esac
done

IMAGE_NAME=${IMAGE_NAME:-"distrisearch/slave:latest"}

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

# ============================================================================
# 2. Listar workers disponibles
# ============================================================================
log_info "Obteniendo lista de workers..."

WORKERS=($(docker node ls --filter "role=worker" --format "{{.Hostname}}"))
NUM_WORKERS=${#WORKERS[@]}

if [ "$NUM_WORKERS" -eq 0 ]; then
    log_warn "No hay workers, desplegando en el manager"
    WORKERS=($(docker node ls --format "{{.Hostname}}" | head -1))
    NUM_WORKERS=1
fi

NUM_REPLICAS=${NUM_REPLICAS:-$NUM_WORKERS}
log_info "Workers disponibles: ${WORKERS[*]}"
log_info "Desplegando $NUM_REPLICAS slaves (Backend+Frontend + MongoDB/Redis local c/u)"

# ============================================================================
# 3. Verificar Master
# ============================================================================
log_info "Verificando que el Master está corriendo..."

if ! docker service ps distrisearch-master --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
    log_error "El Master no está corriendo"
    echo "Ejecuta primero: ./05-deploy-master.sh"
    exit 1
fi

echo -e "Master: ${GREEN}OK${NC}"

# ============================================================================
# 4. Obtener/Construir imagen
# ============================================================================
log_info "Verificando imagen: $IMAGE_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

build_image() {
    if [ -f "$PROJECT_ROOT/docker/slave/Dockerfile" ]; then
        log_info "Construyendo imagen desde $PROJECT_ROOT..."
        docker build -t $IMAGE_NAME -f "$PROJECT_ROOT/docker/slave/Dockerfile" "$PROJECT_ROOT"
    elif [ -f "/opt/distrisearch/code/docker/slave/Dockerfile" ]; then
        log_info "Construyendo imagen desde /opt/distrisearch/code..."
        docker build -t $IMAGE_NAME -f "/opt/distrisearch/code/docker/slave/Dockerfile" "/opt/distrisearch/code"
    else
        log_error "No se encontró el Dockerfile del slave"
        echo "Construye la imagen manualmente:"
        echo "  docker build -t distrisearch/slave:latest -f docker/slave/Dockerfile ."
        exit 1
    fi
}

if [ "$FORCE_REBUILD" = true ]; then
    log_info "Forzando reconstrucción de imagen..."
    build_image
elif docker image inspect $IMAGE_NAME &>/dev/null; then
    log_info "Imagen $IMAGE_NAME encontrada localmente"
else
    log_info "Imagen no encontrada. Construyendo..."
    build_image
fi

# Obtener IP del master
MASTER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

# ============================================================================
# 5. Distribuir imagen a workers (si es necesario)
# ============================================================================
distribute_image_to_worker() {
    local WORKER_HOSTNAME=$1
    local WORKER_IP=$(docker node inspect "$WORKER_HOSTNAME" --format '{{.Status.Addr}}' 2>/dev/null)
    
    if [ -z "$WORKER_IP" ] || [ "$WORKER_IP" = "$MASTER_IP" ]; then
        return 0  # Es el mismo nodo o no se pudo obtener IP
    fi
    
    log_info "Distribuyendo imagen a $WORKER_HOSTNAME ($WORKER_IP)..."
    
    # Método 1: Intentar con SSH + docker load
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "$WORKER_IP" "echo ok" &>/dev/null; then
        docker save "$IMAGE_NAME" | ssh "$WORKER_IP" "docker load"
        if [ $? -eq 0 ]; then
            log_info "  Imagen distribuida via SSH"
            return 0
        fi
    fi
    
    # Método 2: Usar archivo temporal con SCP
    local TEMP_FILE="/tmp/distrisearch-slave-image.tar"
    if docker save "$IMAGE_NAME" -o "$TEMP_FILE" 2>/dev/null; then
        if scp -o BatchMode=yes -o ConnectTimeout=5 "$TEMP_FILE" "$WORKER_IP:/tmp/" &>/dev/null; then
            ssh "$WORKER_IP" "docker load -i /tmp/distrisearch-slave-image.tar && rm /tmp/distrisearch-slave-image.tar" &>/dev/null
            rm -f "$TEMP_FILE"
            if [ $? -eq 0 ]; then
                log_info "  Imagen distribuida via SCP"
                return 0
            fi
        fi
        rm -f "$TEMP_FILE"
    fi
    
    log_warn "  No se pudo distribuir imagen automáticamente a $WORKER_HOSTNAME"
    log_warn "  El worker usará la imagen del caché o fallará si no existe"
    return 1
}

# Distribuir imagen a todos los workers si se reconstruyó
if [ "$FORCE_REBUILD" = true ] || [ "$FORCE_UPDATE" = true ]; then
    log_info "Distribuyendo imagen actualizada a workers..."
    for WORKER in "${WORKERS[@]:0:$NUM_REPLICAS}"; do
        distribute_image_to_worker "$WORKER"
    done
fi

# ============================================================================
# 6. Función para actualizar o crear servicio
# ============================================================================
update_or_create_service() {
    local SERVICE_NAME=$1
    local SERVICE_TYPE=$2  # "mongodb", "redis", "slave"
    local WORKER=$3
    local SLAVE_NUM=$4
    
    # Verificar si el servicio existe
    if docker service inspect "$SERVICE_NAME" &>/dev/null; then
        # El servicio existe, verificar su estado
        local RUNNING_TASKS=$(docker service ps "$SERVICE_NAME" --filter "desired-state=running" --format "{{.CurrentState}}" 2>/dev/null | grep -c "Running" || echo "0")
        
        if [ "$RUNNING_TASKS" -gt 0 ]; then
            if [ "$FORCE_UPDATE" = true ] && [ "$SERVICE_TYPE" = "slave" ]; then
                log_update "Actualizando $SERVICE_NAME con nueva imagen..."
                docker service update --image "$IMAGE_NAME" --force "$SERVICE_NAME"
            else
                log_skip "$SERVICE_NAME (running)"
            fi
        else
            # El servicio existe pero no está corriendo - reiniciar
            log_update "Reiniciando $SERVICE_NAME (estaba detenido)..."
            docker service update --force "$SERVICE_NAME"
        fi
        return 0
    fi
    
    # El servicio no existe, crearlo
    return 1
}

# ============================================================================
# 7. Desplegar stack por cada worker
# ============================================================================
log_info "Desplegando slaves con Backend+Frontend + MongoDB/Redis LOCAL..."

SLAVE_NUM=1
for WORKER in "${WORKERS[@]:0:$NUM_REPLICAS}"; do
    log_info "Procesando slave-$SLAVE_NUM en $WORKER..."
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL para este slave
    # -------------------------------------------------------------------
    if ! update_or_create_service "slave${SLAVE_NUM}-mongodb" "mongodb" "$WORKER" "$SLAVE_NUM"; then
        docker service create \
            --name "slave${SLAVE_NUM}-mongodb" \
            --network distrisearch-network \
            --replicas 1 \
            --no-resolve-image \
            --constraint "node.hostname==$WORKER" \
            --mount type=volume,source="slave${SLAVE_NUM}-mongo-data",target=/data/db \
            mongo:4.4 \
            mongod --bind_ip_all
        
        log_info "  MongoDB local creado para slave-$SLAVE_NUM"
    fi
    
    # -------------------------------------------------------------------
    # Redis LOCAL para este slave
    # -------------------------------------------------------------------
    if ! update_or_create_service "slave${SLAVE_NUM}-redis" "redis" "$WORKER" "$SLAVE_NUM"; then
        docker service create \
            --name "slave${SLAVE_NUM}-redis" \
            --network distrisearch-network \
            --replicas 1 \
            --no-resolve-image \
            --constraint "node.hostname==$WORKER" \
            --mount type=volume,source="slave${SLAVE_NUM}-redis-data",target=/data \
            redis:7-alpine
        
        log_info "  Redis local creado para slave-$SLAVE_NUM"
    fi
    
    # Esperar a que arranquen
    sleep 3
    
    # -------------------------------------------------------------------
    # Slave Node (Backend + Frontend integrado)
    # Puertos: 80 (HTTP), 443 (HTTPS), 8000 (API interna)
    # -------------------------------------------------------------------
    HTTP_PORT=$((8080 + SLAVE_NUM))     # Ej: 8081, 8082...
    HTTPS_PORT=$((4430 + SLAVE_NUM))    # Ej: 4431, 4432...
    API_PORT=$((8001 + SLAVE_NUM))      # Ej: 8002, 8003... (8001 es Master)
    
    if ! update_or_create_service "distrisearch-slave-$SLAVE_NUM" "slave" "$WORKER" "$SLAVE_NUM"; then
        docker service create \
            --name "distrisearch-slave-$SLAVE_NUM" \
            --network distrisearch-network \
            --replicas 1 \
            --no-resolve-image \
            --constraint "node.hostname==$WORKER" \
            --publish published=$HTTP_PORT,target=80 \
            --publish published=$HTTPS_PORT,target=443 \
            --publish published=$API_PORT,target=8000 \
            --env NODE_ID="slave-$SLAVE_NUM" \
            --env NODE_ROLE=slave \
            --env CLUSTER_ID=distrisearch-cluster \
            --env LOCAL_MONGODB_URI="mongodb://slave${SLAVE_NUM}-mongodb:27017" \
            --env MONGODB_URI="mongodb://slave${SLAVE_NUM}-mongodb:27017/distrisearch_slave${SLAVE_NUM}" \
            --env MONGODB_DATABASE="distrisearch_slave${SLAVE_NUM}" \
            --env REDIS_URL="redis://slave${SLAVE_NUM}-redis:6379" \
            --env MASTER_HOST=distrisearch-master \
            --env MASTER_PORT=8001 \
            --env API_PORT=8000 \
            --env NODE_ADDRESS="distrisearch-slave-$SLAVE_NUM" \
            --env REPLICATION_FACTOR=2 \
            --env LOG_LEVEL=INFO \
            --env RAFT_ENABLED=true \
            --mount type=volume,source="slave${SLAVE_NUM}-sqlite",target=/app/data/sqlite \
            --mount type=volume,source="slave${SLAVE_NUM}-raft",target=/app/data/raft \
            --mount type=volume,source="slave${SLAVE_NUM}-docs",target=/app/data/documents \
            --health-cmd "curl -f http://localhost:8000/api/v1/health/live || exit 1" \
            --health-interval 30s \
            --health-timeout 10s \
            --health-retries 3 \
            $IMAGE_NAME
        
        log_info "  Slave-$SLAVE_NUM desplegado en $WORKER"
    fi
    
    log_info "    Frontend: http://<host>:$HTTP_PORT / https://<host>:$HTTPS_PORT"
    log_info "    API:      http://<host>:$API_PORT"
    echo ""
    
    SLAVE_NUM=$((SLAVE_NUM + 1))
done

# ============================================================================
# 8. Esperar a que estén listos
# ============================================================================
log_info "Esperando a que todos los servicios arranquen..."
sleep 10

echo ""
echo "Estado de servicios:"
docker service ls | grep -E "slave|mongo|redis" | head -20

# ============================================================================
# 9. Verificar registro con el Master
# ============================================================================
log_info "Esperando registro de slaves con el Master..."
sleep 15

# Intentar verificar el estado del cluster
CLUSTER_STATUS=$(curl -s http://$MASTER_IP:8000/api/v1/cluster/status 2>/dev/null || echo "{}")

if echo "$CLUSTER_STATUS" | grep -q "nodes"; then
    REGISTERED_NODES=$(echo "$CLUSTER_STATUS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('nodes',[])))" 2>/dev/null || echo "?")
    echo -e "Nodos registrados: ${GREEN}$REGISTERED_NODES${NC}"
else
    log_warn "No se pudo verificar el estado del cluster"
    echo "Verifica manualmente: curl http://$MASTER_IP:8000/api/v1/cluster/status"
fi

# ============================================================================
# 10. Mostrar resumen
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Slaves Desplegados${NC}"
echo "=============================================="
echo ""

echo -e "${BLUE}Arquitectura desplegada (Backend + Frontend integrado):${NC}"
for i in $(seq 1 $((SLAVE_NUM - 1))); do
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    echo "  Slave-$i:"
    echo "    - Frontend HTTP:  puerto $HTTP_PORT (target 80)"
    echo "    - Frontend HTTPS: puerto $HTTPS_PORT (target 443)"
    echo "    - API Backend:    puerto $API_PORT (target 8000)"
    echo "    - MongoDB:        slave${i}-mongodb (LOCAL)"
    echo "    - Redis:          slave${i}-redis (LOCAL)"
    echo "    - SQLite:         /app/data/sqlite/slave-${i}.db"
done

echo ""
echo -e "${BLUE}Configuración:${NC}"
echo "  Usuarios:       SQLite (replicado via Raft)"
echo "  Documentos:     MongoDB LOCAL por nodo"
echo "  Cache:          Redis LOCAL por nodo"
echo "  Registry:       Gossip-based (eventual consistency)"
echo ""
echo -e "${BLUE}Beneficios:${NC}"
echo "  ✓ Frontend integrado en cada slave (no necesita 07-deploy-frontend.sh)"
echo "  ✓ Autenticación funciona durante particiones de red"
echo "  ✓ Cada nodo puede operar independientemente"
echo "  ✓ Sin punto único de fallo para datos"
echo ""

echo -e "${CYAN}URLs de Acceso:${NC}"
for i in $(seq 1 $((SLAVE_NUM - 1))); do
    HTTP_PORT=$((8080 + i))
    HTTPS_PORT=$((4430 + i))
    API_PORT=$((8000 + i))
    echo "  Slave-$i Frontend: http://<worker-ip>:$HTTP_PORT | https://<worker-ip>:$HTTPS_PORT"
    echo "  Slave-$i API:      http://<worker-ip>:$API_PORT"
done
echo ""

echo -e "${BLUE}Opciones del script:${NC}"
echo "  --update   Actualizar imagen en servicios existentes"
echo "  --rebuild  Reconstruir imagen antes de desplegar"
echo ""
echo "Ejemplo para actualizar con nueva imagen:"
echo "  ./06-deploy-slave.sh --rebuild --update"
echo ""

echo "Próximos pasos:"
echo "  1. Verificar cluster: curl http://$MASTER_IP:8000/api/v1/cluster/status"
echo "  2. Ejecutar 08-verify-cluster.sh para verificar el despliegue"
echo ""
echo -e "${GREEN}NOTA:${NC} 07-deploy-frontend.sh NO es necesario - el frontend ya está integrado en cada slave"
echo ""
echo -e "${YELLOW}Ver logs slave:${NC} docker service logs -f distrisearch-slave-1"
echo -e "${YELLOW}Ver logs mongo:${NC} docker service logs -f slave1-mongodb"

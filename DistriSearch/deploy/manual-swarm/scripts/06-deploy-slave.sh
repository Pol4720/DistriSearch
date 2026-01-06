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
# Uso: ./06-deploy-slave.sh [NUM_REPLICAS] [IMAGE_NAME]
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
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1 (ya existe)"; }

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

NUM_REPLICAS=${1:-$NUM_WORKERS}
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
IMAGE_NAME=${2:-"distrisearch/slave:latest"}

log_info "Verificando imagen: $IMAGE_NAME"

if docker image inspect $IMAGE_NAME &>/dev/null; then
    log_skip "Imagen $IMAGE_NAME"
else
    log_info "Imagen no encontrada. Intentando construir..."
    
    # Buscar el Dockerfile del slave
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    
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
fi

# Obtener IP del master
MASTER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

# ============================================================================
# 5. Desplegar stack por cada worker
# ============================================================================
log_info "Desplegando slaves con Backend+Frontend + MongoDB/Redis LOCAL..."

SLAVE_NUM=1
for WORKER in "${WORKERS[@]:0:$NUM_REPLICAS}"; do
    log_info "Desplegando slave-$SLAVE_NUM en $WORKER..."
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL para este slave (verificar si ya existe)
    # -------------------------------------------------------------------
    if docker service inspect "slave${SLAVE_NUM}-mongodb" &>/dev/null; then
        log_skip "slave${SLAVE_NUM}-mongodb"
    else
        docker service create \
            --name "slave${SLAVE_NUM}-mongodb" \
            --network distrisearch-network \
            --replicas 1 \
            --constraint "node.hostname==$WORKER" \
            --mount type=volume,source="slave${SLAVE_NUM}-mongo-data",target=/data/db \
            mongo:7.0 \
            mongod --bind_ip_all
        
        log_info "  MongoDB local creado para slave-$SLAVE_NUM"
    fi
    
    # -------------------------------------------------------------------
    # Redis LOCAL para este slave (verificar si ya existe)
    # -------------------------------------------------------------------
    if docker service inspect "slave${SLAVE_NUM}-redis" &>/dev/null; then
        log_skip "slave${SLAVE_NUM}-redis"
    else
        docker service create \
            --name "slave${SLAVE_NUM}-redis" \
            --network distrisearch-network \
            --replicas 1 \
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
    API_PORT=$((8000 + SLAVE_NUM))      # Ej: 8001, 8002...
    
    if docker service inspect "distrisearch-slave-$SLAVE_NUM" &>/dev/null; then
        log_skip "distrisearch-slave-$SLAVE_NUM"
    else
        docker service create \
            --name "distrisearch-slave-$SLAVE_NUM" \
            --network distrisearch-network \
            --replicas 1 \
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
            --env MASTER_PORT=8000 \
            --env API_PORT=8000 \
            --env NODE_ADDRESS="distrisearch-slave-$SLAVE_NUM" \
            --env REPLICATION_FACTOR=2 \
            --env LOG_LEVEL=INFO \
            --env RAFT_ENABLED=true \
            --mount type=volume,source="slave${SLAVE_NUM}-sqlite",target=/app/data/sqlite \
            --mount type=volume,source="slave${SLAVE_NUM}-raft",target=/app/data/raft \
            --mount type=volume,source="slave${SLAVE_NUM}-docs",target=/app/data/documents \
            --health-cmd "curl -f http://localhost:8000/health || exit 1" \
            --health-interval 30s \
            --health-timeout 10s \
            --health-retries 3 \
            $IMAGE_NAME
        
        log_info "  Slave-$SLAVE_NUM desplegado en $WORKER"
        log_info "    Frontend: http://<host>:$HTTP_PORT / https://<host>:$HTTPS_PORT"
        log_info "    API:      http://<host>:$API_PORT"
    fi
    echo ""
    
    SLAVE_NUM=$((SLAVE_NUM + 1))
done

# ============================================================================
# 6. Esperar a que estén listos
# ============================================================================
log_info "Esperando a que todos los servicios arranquen..."
sleep 10

echo ""
echo "Estado de servicios:"
docker service ls | grep -E "slave|mongo|redis" | head -20

# ============================================================================
# 7. Verificar registro con el Master
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
# 8. Mostrar resumen
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

echo "Próximos pasos:"
echo "  1. Verificar cluster: curl http://$MASTER_IP:8000/api/v1/cluster/status"
echo "  2. Ejecutar 08-verify-cluster.sh para verificar el despliegue"
echo ""
echo -e "${GREEN}NOTA:${NC} 07-deploy-frontend.sh NO es necesario - el frontend ya está integrado en cada slave"
echo ""
echo -e "${YELLOW}Ver logs slave:${NC} docker service logs -f distrisearch-slave-1"
echo -e "${YELLOW}Ver logs mongo:${NC} docker service logs -f slave1-mongodb"

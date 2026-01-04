#!/bin/bash
# ============================================================================
# 06-deploy-slave.sh - Despliega nodos Slave
# ============================================================================
# Cada slave tiene su propia instancia de MongoDB y Redis (LOCAL)
# Esto garantiza disponibilidad durante particiones de red
#
# Ejecutar en el MANAGER para desplegar slaves en los workers
# Uso: ./06-deploy-slave.sh [NUM_REPLICAS]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Desplegar Slaves"
echo "=============================================="
echo "  Arquitectura: MongoDB/Redis LOCAL por nodo"
echo "=============================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
log_info "Desplegando $NUM_REPLICAS slaves (uno por worker)"

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
# 4. Obtener imagen
# ============================================================================
IMAGE_NAME=${2:-"distrisearch/backend:latest"}

log_info "Usando imagen: $IMAGE_NAME"

if ! docker image inspect $IMAGE_NAME &>/dev/null; then
    log_error "Imagen no encontrada: $IMAGE_NAME"
    echo "Construye la imagen primero o usa la correcta"
    exit 1
fi

# Obtener IP del master
MASTER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

# ============================================================================
# 5. Desplegar stack por cada worker
# ============================================================================
log_info "Desplegando slaves con MongoDB/Redis LOCAL..."

# Limpiar servicios anteriores
for i in $(seq 1 10); do
    docker service rm "distrisearch-slave-$i" 2>/dev/null || true
    docker service rm "slave$i-mongodb" 2>/dev/null || true
    docker service rm "slave$i-redis" 2>/dev/null || true
done

SLAVE_NUM=1
for WORKER in "${WORKERS[@]:0:$NUM_REPLICAS}"; do
    log_info "Desplegando slave-$SLAVE_NUM en $WORKER..."
    
    # -------------------------------------------------------------------
    # MongoDB LOCAL para este slave
    # -------------------------------------------------------------------
    docker service create \
        --name "slave${SLAVE_NUM}-mongodb" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --mount type=volume,source="slave${SLAVE_NUM}-mongo-data",target=/data/db \
        mongo:7.0 \
        mongod --bind_ip_all
    
    log_info "  MongoDB local creado para slave-$SLAVE_NUM"
    
    # -------------------------------------------------------------------
    # Redis LOCAL para este slave
    # -------------------------------------------------------------------
    docker service create \
        --name "slave${SLAVE_NUM}-redis" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --mount type=volume,source="slave${SLAVE_NUM}-redis-data",target=/data \
        redis:7-alpine
    
    log_info "  Redis local creado para slave-$SLAVE_NUM"
    
    # Esperar a que arranquen
    sleep 3
    
    # -------------------------------------------------------------------
    # Slave Node (conecta a SU MongoDB/Redis local)
    # -------------------------------------------------------------------
    docker service create \
        --name "distrisearch-slave-$SLAVE_NUM" \
        --network distrisearch-network \
        --replicas 1 \
        --constraint "node.hostname==$WORKER" \
        --publish published=$((8000 + SLAVE_NUM)),target=8000 \
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

echo -e "${BLUE}Arquitectura desplegada:${NC}"
for i in $(seq 1 $((SLAVE_NUM - 1))); do
    echo "  Slave-$i:"
    echo "    - MongoDB: slave${i}-mongodb (LOCAL)"
    echo "    - Redis:   slave${i}-redis (LOCAL)"
    echo "    - SQLite:  /app/data/sqlite/slave-${i}.db"
done

echo ""
echo -e "${BLUE}Configuración:${NC}"
echo "  Usuarios:       SQLite (replicado via Raft)"
echo "  Documentos:     MongoDB LOCAL por nodo"
echo "  Cache:          Redis LOCAL por nodo"
echo "  Registry:       Gossip-based (eventual consistency)"
echo ""
echo -e "${BLUE}Beneficios:${NC}"
echo "  ✓ Autenticación funciona durante particiones"
echo "  ✓ Cada nodo puede operar independientemente"
echo "  ✓ Sin punto único de fallo para datos"
echo ""

echo "Próximos pasos:"
echo "  1. Verificar cluster: curl http://$MASTER_IP:8000/api/v1/cluster/status"
echo "  2. Ejecutar 07-deploy-frontend.sh"
echo "  3. Ejecutar 08-verify-cluster.sh"
echo ""
echo -e "${YELLOW}Ver logs slave:${NC} docker service logs -f distrisearch-slave-1"
echo -e "${YELLOW}Ver logs mongo:${NC} docker service logs -f slave1-mongodb"

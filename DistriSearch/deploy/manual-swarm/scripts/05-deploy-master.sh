#!/bin/bash
# ============================================================================
# 05-deploy-master.sh - Despliega el Master Coordinator
# ============================================================================
# Ejecutar SOLO en el MANAGER
# 
# El Master Coordinator:
# - Gestiona la topología del cluster (nodos, particiones VP-Tree)
# - Coordina el consenso Raft para elección de líder
# - Mantiene la BD de usuarios (SQLite) y la replica a slaves
# - Propaga UserDocumentRegistry via Gossip
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Desplegar Master (AP)"
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
# 2. Verificar dependencias
# ============================================================================
log_info "Verificando servicios de infraestructura..."

check_service() {
    if docker service ps $1 --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
        echo -e "  $1: ${GREEN}OK${NC}"
        return 0
    else
        echo -e "  $1: ${RED}NO ENCONTRADO${NC}"
        return 1
    fi
}

DEPS_OK=true
check_service master-mongo || DEPS_OK=false
check_service master-redis || DEPS_OK=false

if [ "$DEPS_OK" != "true" ]; then
    log_error "Faltan servicios de infraestructura"
    echo "Ejecuta primero: ./04-deploy-infrastructure.sh"
    exit 1
fi

# ============================================================================
# 3. Obtener imagen
# ============================================================================
IMAGE_NAME=${1:-"distrisearch/backend:latest"}

log_info "Usando imagen: $IMAGE_NAME"

# Verificar si la imagen existe localmente
if ! docker image inspect $IMAGE_NAME &>/dev/null; then
    log_warn "Imagen no encontrada localmente"
    echo ""
    echo "Opciones:"
    echo "  1. Construir la imagen localmente desde el código"
    echo "  2. Especificar otra imagen como parámetro"
    echo ""
    read -p "¿Construir imagen desde ./backend? (s/n): " build_confirm
    
    if [ "$build_confirm" == "s" ]; then
        BACKEND_PATH="/opt/distrisearch/code/backend"
        if [ -d "$BACKEND_PATH" ]; then
            log_info "Construyendo imagen..."
            docker build -t $IMAGE_NAME $BACKEND_PATH
        else
            log_error "No se encuentra el código en $BACKEND_PATH"
            echo "Clona el repositorio o especifica la imagen correcta"
            exit 1
        fi
    else
        exit 1
    fi
fi

# ============================================================================
# 4. Crear volumen para datos del Master
# ============================================================================
log_info "Creando volúmenes para el Master..."

docker volume create master-data 2>/dev/null || true
docker volume create master-users-db 2>/dev/null || true

# ============================================================================
# 5. Desplegar Master
# ============================================================================
log_info "Desplegando Master Coordinator..."

# Eliminar servicio anterior si existe
docker service rm distrisearch-master 2>/dev/null || true

# Número de workers en el cluster
NUM_WORKERS=$(docker node ls --format "{{.ID}}" | wc -l)
log_info "Nodos en el cluster: $NUM_WORKERS"

# Obtener IP del manager
MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

docker service create \
    --name distrisearch-master \
    --network distrisearch-network \
    --replicas 1 \
    --constraint 'node.role==manager' \
    --publish 8000:8000 \
    --publish 50051:50051 \
    --mount type=volume,source=master-data,target=/app/data \
    --mount type=volume,source=master-users-db,target=/app/users \
    --mount type=volume,source=master-sqlite,target=/app/data/sqlite \
    --mount type=volume,source=master-raft,target=/app/data/raft \
    --env NODE_TYPE=master \
    --env NODE_ID=master-001 \
    --env NODE_ROLE=master \
    --env NODE_ADDRESS=$MANAGER_IP \
    --env LOCAL_MONGODB_URI=mongodb://master-mongo:27017 \
    --env MONGODB_URI=mongodb://master-mongo:27017/distrisearch_master \
    --env MONGODB_DATABASE=distrisearch_master \
    --env REDIS_URL=redis://master-redis:6379 \
    --env USERS_DB_PATH=/app/users/users.db \
    --env CLUSTER_SIZE=$NUM_WORKERS \
    --env REPLICATION_FACTOR=2 \
    --env LOG_LEVEL=INFO \
    --env RAFT_ELECTION_TIMEOUT_MIN=150 \
    --env RAFT_ELECTION_TIMEOUT_MAX=300 \
    --env RAFT_HEARTBEAT_INTERVAL=50 \
    --env GOSSIP_INTERVAL=1000 \
    --env GOSSIP_FANOUT=3 \
    --health-cmd "curl -f http://localhost:8000/health || exit 1" \
    --health-interval 30s \
    --health-timeout 10s \
    --health-retries 3 \
    $IMAGE_NAME

# ============================================================================
# 6. Esperar a que esté listo
# ============================================================================
log_info "Esperando a que el Master esté listo..."

echo -n "Master: "
for i in {1..60}; do
    if docker service ps distrisearch-master --format "{{.CurrentState}}" | grep -q "Running"; then
        echo -e "${GREEN}OK${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}TIMEOUT${NC}"
        log_error "El Master no arrancó en el tiempo esperado"
        echo "Revisa los logs: docker service logs distrisearch-master"
        exit 1
    fi
    echo -n "."
    sleep 3
done

# Esperar un poco más para que la aplicación inicialice
sleep 5

# ============================================================================
# 7. Verificar API
# ============================================================================
log_info "Verificando API del Master..."

# Intentar conectar a la API
for i in {1..10}; do
    if curl -s -f http://$MANAGER_IP:8000/health &>/dev/null; then
        echo -e "API: ${GREEN}Respondiendo${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        log_warn "API no responde todavía, puede necesitar más tiempo"
    fi
    sleep 3
done

# ============================================================================
# 8. Mostrar estado
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Master Desplegado Correctamente${NC}"
echo "=============================================="
echo ""
log_info "Estado del servicio:"
docker service ls | grep distrisearch-master
echo ""

echo -e "${BLUE}Endpoints disponibles:${NC}"
echo "  API:      http://$MANAGER_IP:8000"
echo "  Health:   http://$MANAGER_IP:8000/health"
echo "  Docs:     http://$MANAGER_IP:8000/docs"
echo "  Cluster:  http://$MANAGER_IP:8000/cluster/status"
echo "  gRPC:     $MANAGER_IP:50051"
echo ""
echo -e "${BLUE}Arquitectura AP del Master:${NC}"
echo "  • MongoDB (master-mongo) → Metadatos cluster, particiones"
echo "  • Redis (master-redis)   → Cache sesiones, coordinación"
echo "  • SQLite (/app/users)    → Base de datos de usuarios"
echo "  • Raft                   → Consenso y replicación de usuarios"
echo "  • Gossip                 → UserDocumentRegistry distribuido"
echo ""
echo -e "${BLUE}Configuración CAP:${NC}"
echo "  Modo:                   AP (Disponibilidad + Tolerancia a Particiones)"
echo "  Factor Replicación:     2"
echo "  Consenso:               Raft"
echo "  Propagación Registry:   Gossip Protocol"
echo ""
echo "Próximos pasos:"
echo "  1. Verificar que el Master responde: curl http://$MANAGER_IP:8000/health"
echo "  2. Ejecutar 06-deploy-slave.sh para desplegar slaves"
echo ""
echo -e "${YELLOW}Ver logs:${NC} docker service logs -f distrisearch-master"

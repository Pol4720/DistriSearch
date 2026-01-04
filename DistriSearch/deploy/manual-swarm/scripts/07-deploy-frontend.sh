#!/bin/bash
# ============================================================================
# 07-deploy-frontend.sh - Despliega el Frontend
# ============================================================================
# Ejecutar en el MANAGER
# Despliega la interfaz web de DistriSearch
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Desplegar Frontend"
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
# 2. Verificar Master
# ============================================================================
log_info "Verificando servicios backend..."

if ! docker service ps distrisearch-master --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
    log_warn "El Master no está corriendo. El frontend necesita el backend."
fi

# ============================================================================
# 3. Obtener imagen
# ============================================================================
IMAGE_NAME=${1:-"distrisearch/frontend:latest"}

log_info "Usando imagen: $IMAGE_NAME"

if ! docker image inspect $IMAGE_NAME &>/dev/null; then
    log_warn "Imagen no encontrada localmente"
    
    FRONTEND_PATH="/opt/distrisearch/code/frontend"
    if [ -d "$FRONTEND_PATH" ]; then
        read -p "¿Construir imagen desde $FRONTEND_PATH? (s/n): " build_confirm
        if [ "$build_confirm" == "s" ]; then
            log_info "Construyendo imagen del frontend..."
            docker build -t $IMAGE_NAME $FRONTEND_PATH
        else
            exit 1
        fi
    else
        log_error "Código del frontend no encontrado"
        exit 1
    fi
fi

# ============================================================================
# 4. Desplegar Frontend
# ============================================================================
log_info "Desplegando Frontend..."

# Eliminar servicio anterior si existe
docker service rm distrisearch-frontend 2>/dev/null || true

# Obtener IP del manager
MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

docker service create \
    --name distrisearch-frontend \
    --network distrisearch-network \
    --replicas 1 \
    --constraint 'node.role==manager' \
    --publish 3000:3000 \
    --env REACT_APP_API_URL=http://$MANAGER_IP:8000 \
    --env REACT_APP_WS_URL=ws://$MANAGER_IP:8000/ws \
    --env NODE_ENV=production \
    --health-cmd "curl -f http://localhost:3000 || exit 1" \
    --health-interval 30s \
    --health-timeout 10s \
    --health-retries 3 \
    $IMAGE_NAME

# ============================================================================
# 5. Esperar
# ============================================================================
log_info "Esperando a que el Frontend arranque..."

echo -n "Frontend: "
for i in {1..30}; do
    if docker service ps distrisearch-frontend --format "{{.CurrentState}}" | grep -q "Running"; then
        echo -e "${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# ============================================================================
# 6. Mostrar estado
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Frontend Desplegado${NC}"
echo "=============================================="
echo ""
log_info "Estado del servicio:"
docker service ls | grep distrisearch-frontend
echo ""

echo -e "${BLUE}Acceso a la aplicación:${NC}"
echo ""
echo "  🌐  http://$MANAGER_IP:3000"
echo ""
echo "  Desde cualquier máquina en la red puedes acceder a esta URL"
echo ""
echo "Próximos pasos:"
echo "  1. Abrir un navegador en http://$MANAGER_IP:3000"
echo "  2. Ejecutar 08-verify-cluster.sh para verificar todo el sistema"

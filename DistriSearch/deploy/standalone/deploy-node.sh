#!/bin/bash
# ============================================================================
# deploy-node.sh - Desplegar un nodo DistriSearch autónomo con docker run
# ============================================================================
# Este script inicia UN contenedor que incluye TODOS los servicios:
# MongoDB + Redis + Backend + Frontend
#
# ARQUITECTURA:
# - USA la red overlay de Docker Swarm para comunicación entre máquinas
# - NO usa Docker Swarm services (no docker service)
# - USA docker run (contenedores simples conectados a red overlay)
# - Cada contenedor es 100% autónomo
# - Si hay partición de red, cada lado sigue funcionando
# - El algoritmo BULLY maneja la elección de líder
#
# REQUISITOS:
# - Docker Swarm inicializado (docker swarm init/join)
# - Red overlay creada: ./init-swarm-network.sh (en manager)
# - Imagen construida: ./build-image.sh
#
# USO:
#   ./deploy-node.sh --node-id node-1 --api-port 8001 --http-port 8081 --https-port 4431
#   ./deploy-node.sh --node-id node-2 --api-port 8002 --http-port 8082 --https-port 4432
#   ./deploy-node.sh --node-id node-3 --api-port 8003 --http-port 8083 --https-port 4433
# ============================================================================

set -e

# Valores por defecto
NODE_ID=""
API_PORT="8001"
HTTP_PORT="8081"
HTTPS_PORT="4431"
IMAGE_NAME="distrisearch/node:standalone"
CONTAINER_PREFIX="distrisearch-node"
DATA_DIR="/var/lib/distrisearch"
NETWORK_NAME="distrisearch-network"

# IPs de las máquinas (cambiar según tu entorno)
# Máquina A: richard-VirtualBox
MACHINE_A_IP="192.168.61.32"
# Máquina B: abel-VirtualBox
MACHINE_B_IP="192.168.61.33"

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

show_help() {
    echo ""
    echo -e "${CYAN}USO:${NC}"
    echo "  $0 --node-id <id> [opciones]"
    echo ""
    echo -e "${CYAN}OPCIONES REQUERIDAS:${NC}"
    echo "  --node-id, -n     ID del nodo (node-1, node-2, node-3)"
    echo ""
    echo -e "${CYAN}OPCIONES:${NC}"
    echo "  --api-port        Puerto para API backend (default: 8001)"
    echo "  --http-port       Puerto HTTP frontend (default: 8081)"
    echo "  --https-port      Puerto HTTPS frontend (default: 4431)"
    echo "  --peers           Lista de peers (IP:puerto,IP:puerto,...)"
    echo "  --network         Red overlay a usar (default: distrisearch-network)"
    echo "  --help, -h        Mostrar esta ayuda"
    echo ""
    echo -e "${CYAN}EJEMPLOS:${NC}"
    echo ""
    echo "  # Nodo 1 en Máquina A (192.168.1.11):"
    echo "  $0 --node-id node-1 --api-port 8001 --http-port 8081 --https-port 4431"
    echo ""
    echo "  # Nodo 2 en Máquina A (192.168.1.11):"
    echo "  $0 --node-id node-2 --api-port 8002 --http-port 8082 --https-port 4432"
    echo ""
    echo "  # Nodo 3 en Máquina B (192.168.1.13):"
    echo "  $0 --node-id node-3 --api-port 8003 --http-port 8083 --https-port 4433"
    echo ""
    exit 0
}

# Parsear argumentos
PEERS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --node-id|-n)
            NODE_ID="$2"
            shift 2
            ;;
        --api-port)
            API_PORT="$2"
            shift 2
            ;;
        --http-port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --https-port)
            HTTPS_PORT="$2"
            shift 2
            ;;
        --peers)
            PEERS="$2"
            shift 2
            ;;
        --network)
            NETWORK_NAME="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Opción desconocida: $1"
            show_help
            ;;
    esac
done

# Validar argumentos requeridos
if [ -z "$NODE_ID" ]; then
    log_error "Se requiere --node-id"
    show_help
fi

# Detectar IP de esta máquina
LOCAL_IP=$(hostname -I | awk '{print $1}')

# Si no se especificaron peers, usar configuración por defecto
if [ -z "$PEERS" ]; then
    # Usar nombres DNS internos de Docker (NO IPs de host!)
    # En la red overlay de Swarm, los contenedores se descubren por DNS
    # Formato: node-X:8000 donde 8000 es el puerto INTERNO del contenedor
    PEERS="node-1:8000,node-2:8000,node-3:8000"
fi

# Dirección interna del nodo (nombre DNS:puerto interno)
NODE_INTERNAL_ADDRESS="${NODE_ID}:8000"

CONTAINER_NAME="${CONTAINER_PREFIX}-${NODE_ID}"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          DESPLEGAR NODO DISTRISEARCH AUTÓNOMO                 ║${NC}"
echo -e "${BLUE}║          (con red overlay de Swarm)                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Configuración:"
echo "   Node ID:      $NODE_ID"
echo "   Container:    $CONTAINER_NAME"
echo "   API Port:     $API_PORT (external) -> 8000 (internal)"
echo "   HTTP Port:    $HTTP_PORT (external) -> 80 (internal)"
echo "   HTTPS Port:   $HTTPS_PORT (external) -> 443 (internal)"
echo "   Local IP:     $LOCAL_IP (host)"
echo "   Node Address: $NODE_INTERNAL_ADDRESS (internal DNS)"
echo "   Peers:        $PEERS (internal DNS names)"
echo "   Network:      $NETWORK_NAME (overlay)"
echo ""

# Verificar si estamos en Swarm
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    log_error "Este nodo no es parte de un Docker Swarm"
    log_info "La red overlay requiere Swarm. Ejecuta:"
    log_info "  - En manager: docker swarm init"
    log_info "  - En workers: docker swarm join --token <token> <manager-ip>:2377"
    exit 1
fi

# Verificar si la red overlay existe
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    log_error "Red overlay '${NETWORK_NAME}' no encontrada"
    log_info "Crea la red primero (desde el manager):"
    log_info "  ./init-swarm-network.sh"
    exit 1
fi

# Verificar si la imagen existe
if ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "$IMAGE_NAME"; then
    log_error "Imagen '$IMAGE_NAME' no encontrada"
    log_info "Construye primero la imagen con: ./build-image.sh"
    exit 1
fi

# Detener contenedor existente si existe
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warn "Deteniendo contenedor existente: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Crear directorio de datos para persistencia
NODE_DATA_DIR="${DATA_DIR}/${NODE_ID}"
sudo mkdir -p "${NODE_DATA_DIR}/mongodb"
sudo mkdir -p "${NODE_DATA_DIR}/redis"
sudo mkdir -p "${NODE_DATA_DIR}/uploads"
log_info "Directorio de datos: $NODE_DATA_DIR"

# Ejecutar el contenedor
log_info "Iniciando contenedor..."

# Ejecutar el contenedor CON RED OVERLAY
log_info "Iniciando contenedor..."

docker run -d \
    --name "$CONTAINER_NAME" \
    --hostname "$NODE_ID" \
    --network "$NETWORK_NAME" \
    --network-alias "$NODE_ID" \
    -p "${API_PORT}:8000" \
    -p "${HTTP_PORT}:80" \
    -p "${HTTPS_PORT}:443" \
    -v "${NODE_DATA_DIR}/mongodb:/data/db" \
    -v "${NODE_DATA_DIR}/redis:/data/redis" \
    -v "${NODE_DATA_DIR}/uploads:/app/uploads" \
    -e "NODE_ID=${NODE_ID}" \
    -e "NODE_ADDRESS=${NODE_INTERNAL_ADDRESS}" \
    -e "NODE_ROLE=slave" \
    -e "BULLY_PEERS=${PEERS}" \
    -e "BULLY_ENABLED=true" \
    -e "API_PORT=8000" \
    -e "MONGODB_HOST=127.0.0.1" \
    -e "MONGODB_PORT=27017" \
    -e "REDIS_HOST=127.0.0.1" \
    -e "REDIS_PORT=6379" \
    -e "SECRET_KEY=distrisearch-$(date +%s)" \
    -e "LOG_LEVEL=INFO" \
    --restart=no \
    "$IMAGE_NAME"

# Verificar que el contenedor esté corriendo
sleep 2
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "✅ Contenedor iniciado exitosamente"
    
    # Esperar a que los servicios estén listos
    log_info "Esperando a que los servicios estén listos..."
    for i in {1..30}; do
        if curl -s "http://localhost:${API_PORT}/health" > /dev/null 2>&1; then
            log_info "✅ API disponible en http://localhost:${API_PORT}"
            break
        fi
        sleep 1
    done
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    NODO DESPLEGADO                            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Nodo:          $NODE_ID"
    echo "  Contenedor:    $CONTAINER_NAME"
    echo ""
    echo "  URLs:"
    echo "    API:         http://localhost:${API_PORT}"
    echo "    API:         http://${LOCAL_IP}:${API_PORT}"
    echo "    Frontend:    http://localhost:${HTTP_PORT}"
    echo "    Frontend:    https://localhost:${HTTPS_PORT}"
    echo ""
    echo "  Comandos útiles:"
    echo "    Ver logs:     docker logs -f $CONTAINER_NAME"
    echo "    Detener:      docker stop $CONTAINER_NAME"
    echo "    Reiniciar:    docker start $CONTAINER_NAME"
    echo "    Eliminar:     docker rm -f $CONTAINER_NAME"
    echo ""
else
    log_error "❌ Error iniciando el contenedor"
    log_error "Ver logs: docker logs $CONTAINER_NAME"
    exit 1
fi

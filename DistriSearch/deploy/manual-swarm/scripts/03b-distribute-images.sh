#!/bin/bash
# ============================================================================
# 03b-distribute-images.sh - Distribuir imágenes Docker a nodos workers
# ============================================================================
# Este script exporta las imágenes necesarias desde el manager y las carga
# en todos los workers del swarm vía SSH.
#
# Ejecutar en el MANAGER después de que los workers se hayan unido al swarm.
# 
# Requisitos:
# - SSH sin contraseña configurado a los workers (ssh-copy-id)
# - Las imágenes ya construidas en el manager
#
# Uso: ./03b-distribute-images.sh [--rebuild]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Distribuir Imágenes"
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

REBUILD=false
for arg in "$@"; do
    case $arg in
        --rebuild)
            REBUILD=true
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

# ============================================================================
# 2. Obtener lista de workers con sus IPs
# ============================================================================
log_info "Obteniendo lista de workers..."

MANAGER_HOSTNAME=$(hostname)
declare -A WORKER_IPS

# Obtener workers (nodos que no son managers)
while IFS= read -r line; do
    NODE_ID=$(echo "$line" | awk '{print $1}')
    NODE_HOSTNAME=$(echo "$line" | awk '{print $2}')
    NODE_STATUS=$(echo "$line" | awk '{print $3}')
    IS_MANAGER_ROLE=$(echo "$line" | awk '{print $5}')
    
    # Solo workers activos (no managers)
    if [ "$NODE_STATUS" = "Ready" ] && [ "$IS_MANAGER_ROLE" = "" ] && [ "$NODE_HOSTNAME" != "$MANAGER_HOSTNAME" ]; then
        # Obtener IP del nodo
        NODE_IP=$(docker node inspect "$NODE_ID" --format '{{.Status.Addr}}' 2>/dev/null)
        if [ -n "$NODE_IP" ]; then
            WORKER_IPS["$NODE_HOSTNAME"]="$NODE_IP"
            log_info "Worker encontrado: $NODE_HOSTNAME ($NODE_IP)"
        fi
    fi
done < <(docker node ls --format "{{.ID}} {{.Hostname}} {{.Status}} {{.Availability}} {{.ManagerStatus}}")

if [ ${#WORKER_IPS[@]} -eq 0 ]; then
    log_warn "No hay workers en el cluster. Las imágenes solo estarán en el manager."
    exit 0
fi

# ============================================================================
# 3. Construir imágenes si es necesario
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TEMP_DIR="/tmp/distrisearch-images"

mkdir -p "$TEMP_DIR"

IMAGES=(
    "distrisearch/slave:latest"
    "distrisearch/load-balancer:latest"
    "distrisearch/coredns:latest"
)

build_if_missing() {
    local IMAGE_NAME=$1
    local DOCKERFILE=$2
    local BUILD_CONTEXT=$3
    
    if [ "$REBUILD" = true ] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
        if [ -f "$DOCKERFILE" ]; then
            log_info "Construyendo $IMAGE_NAME..."
            docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$BUILD_CONTEXT"
        else
            log_warn "No se encontró Dockerfile para $IMAGE_NAME: $DOCKERFILE"
        fi
    else
        log_skip "Imagen $IMAGE_NAME ya existe"
    fi
}

# Construir imágenes si no existen
build_if_missing "distrisearch/slave:latest" "$PROJECT_ROOT/docker/slave/Dockerfile" "$PROJECT_ROOT"
build_if_missing "distrisearch/load-balancer:latest" "$PROJECT_ROOT/docker/load-balancer/Dockerfile" "$PROJECT_ROOT/docker/load-balancer"
build_if_missing "distrisearch/coredns:latest" "$PROJECT_ROOT/docker/coredns/Dockerfile" "$PROJECT_ROOT/docker/coredns"

# ============================================================================
# 4. Exportar imágenes a archivos tar
# ============================================================================
log_info "Exportando imágenes..."

for IMAGE in "${IMAGES[@]}"; do
    IMAGE_FILE=$(echo "$IMAGE" | sed 's/\//-/g' | sed 's/:/-/g').tar.gz
    IMAGE_PATH="$TEMP_DIR/$IMAGE_FILE"
    
    if [ -f "$IMAGE_PATH" ] && [ "$REBUILD" != true ]; then
        log_skip "Archivo $IMAGE_FILE ya existe"
    else
        log_info "Guardando $IMAGE -> $IMAGE_FILE..."
        docker save "$IMAGE" | gzip > "$IMAGE_PATH"
    fi
done

# También incluir imágenes base que se necesitan
BASE_IMAGES=(
    "mongo:4.4"
    "redis:7-alpine"
)

for IMAGE in "${BASE_IMAGES[@]}"; do
    # Descargar si no existe
    if ! docker image inspect "$IMAGE" &>/dev/null; then
        log_info "Descargando imagen base $IMAGE..."
        docker pull "$IMAGE"
    fi
    
    IMAGE_FILE=$(echo "$IMAGE" | sed 's/\//-/g' | sed 's/:/-/g').tar.gz
    IMAGE_PATH="$TEMP_DIR/$IMAGE_FILE"
    
    if [ -f "$IMAGE_PATH" ]; then
        log_skip "Archivo $IMAGE_FILE ya existe"
    else
        log_info "Guardando $IMAGE -> $IMAGE_FILE..."
        docker save "$IMAGE" | gzip > "$IMAGE_PATH"
    fi
done

# ============================================================================
# 5. Transferir y cargar imágenes en cada worker
# ============================================================================
log_info "Transfiriendo imágenes a workers..."
echo ""

ALL_IMAGES=("${IMAGES[@]}" "${BASE_IMAGES[@]}")

for HOSTNAME in "${!WORKER_IPS[@]}"; do
    IP="${WORKER_IPS[$HOSTNAME]}"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Procesando: $HOSTNAME ($IP)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Verificar conexión SSH
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$IP" "echo ok" &>/dev/null; then
        log_warn "No se puede conectar a $HOSTNAME ($IP) vía SSH"
        log_warn "Asegúrate de ejecutar: ssh-copy-id $IP"
        continue
    fi
    
    # Crear directorio temporal en worker
    ssh "$IP" "mkdir -p /tmp/distrisearch-images"
    
    for IMAGE in "${ALL_IMAGES[@]}"; do
        IMAGE_FILE=$(echo "$IMAGE" | sed 's/\//-/g' | sed 's/:/-/g').tar.gz
        IMAGE_PATH="$TEMP_DIR/$IMAGE_FILE"
        
        # Verificar si la imagen ya existe en el worker
        if ssh "$IP" "docker image inspect '$IMAGE' &>/dev/null" 2>/dev/null; then
            log_skip "$IMAGE ya existe en $HOSTNAME"
            continue
        fi
        
        # Transferir archivo
        log_info "Transfiriendo $IMAGE_FILE a $HOSTNAME..."
        scp -q "$IMAGE_PATH" "$IP:/tmp/distrisearch-images/"
        
        # Cargar imagen en worker
        log_info "Cargando $IMAGE en $HOSTNAME..."
        ssh "$IP" "gunzip -c /tmp/distrisearch-images/$IMAGE_FILE | docker load"
    done
    
    # Limpiar archivos temporales en worker
    ssh "$IP" "rm -rf /tmp/distrisearch-images"
    
    echo -e "  ${GREEN}✓${NC} $HOSTNAME completado"
    echo ""
done

# ============================================================================
# 6. Limpieza local
# ============================================================================
log_info "Limpiando archivos temporales..."
rm -rf "$TEMP_DIR"

# ============================================================================
# 7. Verificar imágenes en todos los nodos
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Verificación de Imágenes${NC}"
echo "=============================================="
echo ""

echo -e "${CYAN}Manager ($MANAGER_HOSTNAME):${NC}"
for IMAGE in "${IMAGES[@]}"; do
    if docker image inspect "$IMAGE" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $IMAGE"
    else
        echo -e "  ${RED}✗${NC} $IMAGE"
    fi
done

for HOSTNAME in "${!WORKER_IPS[@]}"; do
    IP="${WORKER_IPS[$HOSTNAME]}"
    echo ""
    echo -e "${CYAN}Worker $HOSTNAME ($IP):${NC}"
    
    for IMAGE in "${IMAGES[@]}"; do
        if ssh "$IP" "docker image inspect '$IMAGE' &>/dev/null" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $IMAGE"
        else
            echo -e "  ${RED}✗${NC} $IMAGE"
        fi
    done
done

echo ""
log_info "Distribución de imágenes completada"
echo ""
echo -e "${YELLOW}Siguiente paso:${NC}"
echo "  ./04-deploy-infrastructure-ha.sh"
echo ""

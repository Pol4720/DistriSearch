#!/bin/bash
# ============================================================================
# build-image.sh - Construir imagen DistriSearch Standalone
# ============================================================================
# Este script construye la imagen Docker all-in-one que contiene:
# MongoDB + Redis + Backend + Frontend
#
# USO:
#   ./build-image.sh              # Construir con cache
#   ./build-image.sh --no-cache   # Construir desde cero
#   ./build-image.sh --push       # Construir y exportar a archivo
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
IMAGE_NAME="distrisearch/node:standalone"
IMAGE_FILE="distrisearch-node-standalone.tar"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parsear argumentos
NO_CACHE=""
EXPORT_IMAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --push|--export)
            EXPORT_IMAGE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     CONSTRUIR IMAGEN DISTRISEARCH STANDALONE                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Directorio del proyecto: $PROJECT_ROOT"
log_info "Imagen: $IMAGE_NAME"

# Verificar que existan los archivos necesarios
if [ ! -f "$PROJECT_ROOT/docker/node-standalone/Dockerfile" ]; then
    log_error "No se encuentra el Dockerfile en docker/node-standalone/"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/backend" ]; then
    log_error "No se encuentra el directorio backend/"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/frontend" ]; then
    log_error "No se encuentra el directorio frontend/"
    exit 1
fi

# Construir la imagen
log_info "Construyendo imagen Docker..."
cd "$PROJECT_ROOT"

docker build \
    $NO_CACHE \
    -t "$IMAGE_NAME" \
    -f docker/node-standalone/Dockerfile \
    .

if [ $? -eq 0 ]; then
    log_info "✅ Imagen construida exitosamente: $IMAGE_NAME"
    
    # Mostrar tamaño de la imagen
    SIZE=$(docker images "$IMAGE_NAME" --format "{{.Size}}")
    log_info "   Tamaño: $SIZE"
    
    # Exportar si se solicitó
    if [ "$EXPORT_IMAGE" = true ]; then
        log_info "Exportando imagen a archivo..."
        docker save "$IMAGE_NAME" -o "$SCRIPT_DIR/$IMAGE_FILE"
        log_info "✅ Imagen exportada a: $SCRIPT_DIR/$IMAGE_FILE"
        log_info "   Para cargar en otra máquina: docker load -i $IMAGE_FILE"
    fi
else
    log_error "❌ Error construyendo la imagen"
    exit 1
fi

echo ""
log_info "Para desplegar un nodo, usa:"
echo "   ./deploy-node.sh --node-id node-1 --port 8001"
echo ""

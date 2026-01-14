#!/bin/bash
# ============================================================================
# transfer-image.sh - Transferir imagen Docker a otra máquina
# ============================================================================
# Este script exporta la imagen y la transfiere a otra máquina via SSH/SCP
#
# USO:
#   ./transfer-image.sh <usuario@ip_destino>
#   ./transfer-image.sh richard@192.168.1.13
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="distrisearch/node:standalone"
IMAGE_FILE="distrisearch-node-standalone.tar"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ -z "$1" ]; then
    log_error "Uso: $0 <usuario@ip_destino>"
    log_info "Ejemplo: $0 richard@192.168.1.13"
    exit 1
fi

DESTINATION="$1"

# Verificar que la imagen exista
if ! docker images "$IMAGE_NAME" --format "{{.Repository}}:{{.Tag}}" | grep -q "$IMAGE_NAME"; then
    log_error "Imagen '$IMAGE_NAME' no encontrada"
    log_info "Construye primero la imagen con: ./build-image.sh"
    exit 1
fi

# Exportar imagen
log_info "Exportando imagen a archivo..."
docker save "$IMAGE_NAME" -o "$SCRIPT_DIR/$IMAGE_FILE"
log_info "Imagen exportada: $SCRIPT_DIR/$IMAGE_FILE"

# Obtener tamaño
SIZE=$(du -h "$SCRIPT_DIR/$IMAGE_FILE" | cut -f1)
log_info "Tamaño del archivo: $SIZE"

# Transferir
log_info "Transfiriendo imagen a $DESTINATION..."
scp "$SCRIPT_DIR/$IMAGE_FILE" "${DESTINATION}:~/"

log_info "✅ Imagen transferida"
log_info ""
log_info "En la máquina destino, ejecuta:"
echo "   docker load -i ~/$IMAGE_FILE"
echo ""

# Limpiar archivo local (opcional)
read -p "¿Eliminar archivo local? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    rm -f "$SCRIPT_DIR/$IMAGE_FILE"
    log_info "Archivo local eliminado"
fi

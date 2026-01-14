#!/bin/bash
# ============================================================================
# cleanup.sh - Limpiar completamente el despliegue de DistriSearch
# ============================================================================
# Este script elimina:
# - Todos los contenedores distrisearch-node-*
# - Todos los datos persistentes en /var/lib/distrisearch
# - Opcionalmente los volúmenes Docker huérfanos
#
# USO:
#   ./cleanup.sh              # Limpieza completa
#   ./cleanup.sh --keep-data  # Solo detener contenedores, mantener datos
#   ./cleanup.sh --all        # Limpieza completa + volúmenes Docker huérfanos
# ============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

KEEP_DATA=false
PRUNE_VOLUMES=false
DATA_DIR="/var/lib/distrisearch"
CONTAINER_PREFIX="distrisearch-node"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --all)
            PRUNE_VOLUMES=true
            shift
            ;;
        --help|-h)
            echo ""
            echo "USO: $0 [opciones]"
            echo ""
            echo "OPCIONES:"
            echo "  (sin args)     Limpieza completa: contenedores + datos"
            echo "  --keep-data    Solo detener contenedores, mantener datos"
            echo "  --all          Limpieza completa + volúmenes Docker huérfanos"
            echo "  --help, -h     Mostrar esta ayuda"
            echo ""
            exit 0
            ;;
        *)
            log_error "Opción desconocida: $1"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          LIMPIEZA DE DESPLIEGUE DISTRISEARCH                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Encontrar y detener todos los contenedores distrisearch-node-*
log_info "Buscando contenedores DistriSearch..."
CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep "^${CONTAINER_PREFIX}" || true)

if [ -n "$CONTAINERS" ]; then
    log_info "Contenedores encontrados:"
    echo "$CONTAINERS" | while read container; do
        echo "   - $container"
    done
    echo ""
    
    log_info "Deteniendo contenedores..."
    echo "$CONTAINERS" | while read container; do
        docker stop "$container" 2>/dev/null || true
        log_info "  ✓ Detenido: $container"
    done
    
    log_info "Eliminando contenedores..."
    echo "$CONTAINERS" | while read container; do
        docker rm "$container" 2>/dev/null || true
        log_info "  ✓ Eliminado: $container"
    done
else
    log_info "No se encontraron contenedores DistriSearch"
fi

# 2. Eliminar datos persistentes
if [ "$KEEP_DATA" = false ]; then
    if [ -d "$DATA_DIR" ]; then
        log_info "Eliminando datos persistentes en $DATA_DIR..."
        
        # Mostrar qué se va a eliminar
        if [ -n "$(ls -A $DATA_DIR 2>/dev/null)" ]; then
            echo "   Datos a eliminar:"
            ls -la "$DATA_DIR" | tail -n +4 | while read line; do
                echo "     $line"
            done
            echo ""
        fi
        
        sudo rm -rf "${DATA_DIR}"/*
        log_info "✅ Datos eliminados"
    else
        log_info "No hay datos en $DATA_DIR"
    fi
else
    log_warn "Manteniendo datos en $DATA_DIR (--keep-data)"
fi

# 3. Limpiar volúmenes huérfanos (opcional)
if [ "$PRUNE_VOLUMES" = true ]; then
    log_info "Limpiando volúmenes Docker huérfanos..."
    docker volume prune -f
    log_info "✅ Volúmenes limpiados"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 LIMPIEZA COMPLETADA                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$KEEP_DATA" = false ]; then
    echo "  ✅ Contenedores eliminados"
    echo "  ✅ Datos persistentes eliminados"
    echo ""
    echo "  El sistema está listo para un despliegue limpio:"
    echo "    ./deploy-node.sh --node-id node-1"
    echo "    ./deploy-node.sh --node-id node-2"
else
    echo "  ✅ Contenedores eliminados"
    echo "  ⚠️  Datos persistentes mantenidos en $DATA_DIR"
    echo ""
    echo "  Los datos se restaurarán en el próximo despliegue."
fi
echo ""

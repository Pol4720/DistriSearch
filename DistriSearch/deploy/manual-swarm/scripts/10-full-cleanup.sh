#!/bin/bash
# ============================================================================
# 10-full-cleanup.sh - Limpieza TOTAL del entorno DistriSearch
# ============================================================================
# Este script elimina TODOS los recursos de DistriSearch incluyendo:
#   - Servicios Swarm
#   - Volúmenes de datos (MongoDB, Redis)
#   - Redes overlay
#   - Salir del Swarm
#   - Contenedores huérfanos
#
# Uso: ./10-full-cleanup.sh [--force]
#   --force: No pedir confirmación
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - LIMPIEZA TOTAL"
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
log_step() { echo -e "${CYAN}[PASO]${NC} $1"; }

# Parsear argumentos
FORCE=false
for arg in "$@"; do
    case $arg in
        --force|-f)
            FORCE=true
            ;;
    esac
done

# ============================================================================
# Mostrar qué se va a eliminar
# ============================================================================
echo ""
echo -e "${RED}⚠️  ADVERTENCIA: Este script realizará una limpieza TOTAL${NC}"
echo ""
echo "Se eliminarán:"
echo "  ❌ TODOS los servicios de DistriSearch"
echo "  ❌ TODOS los volúmenes de datos (MongoDB, Redis) - DATOS PERDIDOS"
echo "  ❌ La red overlay distrisearch-network"
echo "  ❌ Este nodo saldrá del Swarm"
echo "  ❌ Contenedores y volúmenes huérfanos"
echo ""

if [ "$FORCE" != true ]; then
    echo -e "${YELLOW}¿Estás SEGURO de que quieres continuar?${NC}"
    read -p "Escribe 'SI' para confirmar: " confirm
    if [ "$confirm" != "SI" ]; then
        echo "Cancelado"
        exit 0
    fi
fi

# ============================================================================
# PASO 1: Verificar si estamos en un Swarm
# ============================================================================
log_step "Verificando estado del Swarm..."

SWARM_STATE=$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo "inactive")
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null || echo "false")

echo "  Estado Swarm: $SWARM_STATE"
echo "  Es Manager: $IS_MANAGER"

# ============================================================================
# PASO 2: Eliminar servicios (si somos manager)
# ============================================================================
if [ "$IS_MANAGER" = "true" ]; then
    log_step "Eliminando TODOS los servicios de DistriSearch..."
    
    # Listar todos los servicios y eliminar los de DistriSearch
    SERVICES=$(docker service ls --format "{{.Name}}" 2>/dev/null | grep -E "distrisearch|node|slave|master|redis|mongodb|coredns|load-balancer|coordinator" || true)
    
    if [ -n "$SERVICES" ]; then
        echo "$SERVICES" | while read svc; do
            docker service rm "$svc" 2>/dev/null && echo "  ✓ Eliminado servicio: $svc" || true
        done
    else
        echo "  No hay servicios de DistriSearch"
    fi
    
    # Esperar a que los servicios se detengan
    log_info "Esperando 10 segundos para que los servicios se detengan..."
    sleep 10
fi

# ============================================================================
# PASO 3: Salir del Swarm
# ============================================================================
if [ "$SWARM_STATE" = "active" ]; then
    log_step "Saliendo del Swarm..."
    
    if [ "$IS_MANAGER" = "true" ]; then
        docker swarm leave --force 2>/dev/null && echo "  ✓ Salió del Swarm (manager)" || log_warn "No se pudo salir del Swarm"
    else
        docker swarm leave 2>/dev/null && echo "  ✓ Salió del Swarm (worker)" || log_warn "No se pudo salir del Swarm"
    fi
    
    # Esperar un momento después de salir
    sleep 3
else
    echo "  No estamos en un Swarm activo"
fi

# ============================================================================
# PASO 4: Eliminar volúmenes de DistriSearch
# ============================================================================
log_step "Eliminando volúmenes de datos..."

# Patrones de volúmenes a eliminar
VOLUME_PATTERNS="node[0-9]|slave[0-9]|master-|coordinator-|distrisearch|mongodb|redis"

VOLUMES=$(docker volume ls --format "{{.Name}}" 2>/dev/null | grep -E "$VOLUME_PATTERNS" || true)

if [ -n "$VOLUMES" ]; then
    echo "$VOLUMES" | while read vol; do
        docker volume rm "$vol" 2>/dev/null && echo "  ✓ Eliminado volumen: $vol" || echo "  ⚠ No se pudo eliminar: $vol"
    done
else
    echo "  No hay volúmenes de DistriSearch"
fi

# ============================================================================
# PASO 5: Eliminar redes de DistriSearch
# ============================================================================
log_step "Eliminando redes..."

NETWORKS=$(docker network ls --format "{{.Name}}" 2>/dev/null | grep -E "distrisearch" || true)

if [ -n "$NETWORKS" ]; then
    echo "$NETWORKS" | while read net; do
        docker network rm "$net" 2>/dev/null && echo "  ✓ Eliminada red: $net" || echo "  ⚠ No se pudo eliminar: $net"
    done
else
    echo "  No hay redes de DistriSearch"
fi

# ============================================================================
# PASO 6: Limpiar contenedores huérfanos
# ============================================================================
log_step "Limpiando contenedores huérfanos..."

# Eliminar contenedores detenidos relacionados con DistriSearch
CONTAINERS=$(docker ps -a --format "{{.Names}}" 2>/dev/null | grep -E "distrisearch|node|slave|master|coredns|load-balancer" || true)

if [ -n "$CONTAINERS" ]; then
    echo "$CONTAINERS" | while read container; do
        docker rm -f "$container" 2>/dev/null && echo "  ✓ Eliminado contenedor: $container" || true
    done
else
    echo "  No hay contenedores huérfanos"
fi

# ============================================================================
# PASO 7: Limpiar recursos Docker huérfanos (prune)
# ============================================================================
log_step "Limpiando recursos Docker huérfanos..."

echo "  Limpiando volúmenes no utilizados..."
docker volume prune -f 2>/dev/null | grep -E "Total|deleted" || true

echo "  Limpiando redes no utilizadas..."
docker network prune -f 2>/dev/null | grep -E "Total|deleted" || true

# ============================================================================
# PASO 8: Eliminar archivos de configuración temporal
# ============================================================================
log_step "Limpiando archivos de configuración..."

if [ -d "/opt/distrisearch" ]; then
    rm -rf /opt/distrisearch/config/swarm-tokens.env 2>/dev/null && echo "  ✓ Eliminados tokens de Swarm" || true
fi

# ============================================================================
# Resumen final
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  ✅ LIMPIEZA TOTAL COMPLETADA${NC}"
echo "=============================================="
echo ""

echo -e "${CYAN}Estado final:${NC}"
echo ""

echo "Servicios Docker:"
docker service ls 2>/dev/null || echo "  (No estamos en un Swarm)"

echo ""
echo "Volúmenes restantes:"
docker volume ls --format "{{.Name}}" | head -10 || echo "  (ninguno)"
TOTAL_VOLUMES=$(docker volume ls -q | wc -l)
echo "  Total: $TOTAL_VOLUMES volúmenes"

echo ""
echo "Redes Docker:"
docker network ls --format "{{.Name}}" | grep -v -E "^bridge$|^host$|^none$" | head -5 || echo "  (solo redes por defecto)"

echo ""
echo -e "${GREEN}Para comenzar de nuevo:${NC}"
echo "  1. cd $(dirname $0)"
echo "  2. ./02-init-swarm.sh"
echo "  3. (En workers) docker swarm join ..."
echo "  4. ./04-deploy-infrastructure-ha.sh"
echo "  5. ./05-deploy-nodes-ha.sh"
echo ""

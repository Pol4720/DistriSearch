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
# Uso: ./10-full-cleanup.sh [OPCIONES]
#
# Opciones:
#   --force, -f         No pedir confirmación
#   --services-only     Solo eliminar servicios (no salir del Swarm)
#   --volumes-only      Solo eliminar volúmenes
#   --networks-only     Solo eliminar redes
#   --keep-swarm        No salir del Swarm
#   --keep-volumes      No eliminar volúmenes de datos
#   --nodes N           Número de nodos a limpiar (por defecto: 10)
#   --prefix PREFIX     Prefijo de servicios (por defecto: distrisearch)
#   --prune             Incluir docker system prune al final
#   --help, -h          Mostrar esta ayuda
#
# Ejemplos:
#   ./10-full-cleanup.sh --force                    # Limpieza total sin confirmación
#   ./10-full-cleanup.sh --services-only --force    # Solo servicios
#   ./10-full-cleanup.sh --keep-swarm --keep-volumes # Limpiar pero mantener swarm y datos
#   ./10-full-cleanup.sh --nodes 5 --prefix myapp   # 5 nodos con prefijo personalizado
# ============================================================================

set -e

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

# Valores por defecto
FORCE=false
SERVICES_ONLY=false
VOLUMES_ONLY=false
NETWORKS_ONLY=false
KEEP_SWARM=false
KEEP_VOLUMES=false
DO_PRUNE=false
MAX_NODES=10
SERVICE_PREFIX="distrisearch"

show_help() {
    head -35 "$0" | tail -30
    exit 0
}

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        --services-only)
            SERVICES_ONLY=true
            shift
            ;;
        --volumes-only)
            VOLUMES_ONLY=true
            shift
            ;;
        --networks-only)
            NETWORKS_ONLY=true
            shift
            ;;
        --keep-swarm)
            KEEP_SWARM=true
            shift
            ;;
        --keep-volumes)
            KEEP_VOLUMES=true
            shift
            ;;
        --prune)
            DO_PRUNE=true
            shift
            ;;
        --nodes)
            MAX_NODES="$2"
            shift 2
            ;;
        --prefix)
            SERVICE_PREFIX="$2"
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

echo "=============================================="
echo "  DistriSearch - LIMPIEZA TOTAL"
echo "=============================================="
echo ""
echo "Configuración:"
echo "  Prefijo: $SERVICE_PREFIX"
echo "  Max nodos: $MAX_NODES"
echo "  Mantener Swarm: $KEEP_SWARM"
echo "  Mantener volúmenes: $KEEP_VOLUMES"
[ "$SERVICES_ONLY" = true ] && echo "  Modo: Solo servicios"
[ "$VOLUMES_ONLY" = true ] && echo "  Modo: Solo volúmenes"
[ "$NETWORKS_ONLY" = true ] && echo "  Modo: Solo redes"

# ============================================================================
# Mostrar qué se va a eliminar
# ============================================================================
echo ""
if [ "$SERVICES_ONLY" != true ] && [ "$VOLUMES_ONLY" != true ] && [ "$NETWORKS_ONLY" != true ]; then
    echo -e "${RED}⚠️  ADVERTENCIA: Este script realizará una limpieza TOTAL${NC}"
    echo ""
    echo "Se eliminarán:"
    echo "  ❌ TODOS los servicios de DistriSearch"
    [ "$KEEP_VOLUMES" != true ] && echo "  ❌ TODOS los volúmenes de datos (MongoDB, Redis) - DATOS PERDIDOS"
    echo "  ❌ La red overlay distrisearch-network"
    [ "$KEEP_SWARM" != true ] && echo "  ❌ Este nodo saldrá del Swarm"
    echo "  ❌ Contenedores y volúmenes huérfanos"
else
    echo -e "${YELLOW}Modo selectivo de limpieza${NC}"
    [ "$SERVICES_ONLY" = true ] && echo "  - Solo servicios"
    [ "$VOLUMES_ONLY" = true ] && echo "  - Solo volúmenes"
    [ "$NETWORKS_ONLY" = true ] && echo "  - Solo redes"
fi
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
if [ "$VOLUMES_ONLY" != true ] && [ "$NETWORKS_ONLY" != true ]; then
    if [ "$IS_MANAGER" = "true" ]; then
        log_step "Eliminando servicios de DistriSearch..."
        
        # Generar patrón dinámico para nodos 1..N
        NODE_PATTERN=""
        for i in $(seq 1 $MAX_NODES); do
            [ -n "$NODE_PATTERN" ] && NODE_PATTERN="$NODE_PATTERN|"
            NODE_PATTERN="${NODE_PATTERN}${SERVICE_PREFIX}-node-${i}|${SERVICE_PREFIX}-mongodb-${i}|${SERVICE_PREFIX}-redis-${i}"
        done
        
        # Patrón completo incluyendo servicios de infraestructura
        FULL_PATTERN="${NODE_PATTERN}|${SERVICE_PREFIX}|coredns|load-balancer|coordinator|master"
        
        # Listar todos los servicios y eliminar los que coincidan
        SERVICES=$(docker service ls --format "{{.Name}}" 2>/dev/null | grep -E "$FULL_PATTERN" || true)
        
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
    
    # Si solo queremos servicios, terminar aquí
    if [ "$SERVICES_ONLY" = true ]; then
        log_info "Limpieza de servicios completada (modo --services-only)"
        exit 0
    fi
fi

# ============================================================================
# PASO 3: Salir del Swarm
# ============================================================================
if [ "$KEEP_SWARM" != true ] && [ "$VOLUMES_ONLY" != true ] && [ "$NETWORKS_ONLY" != true ] && [ "$SERVICES_ONLY" != true ]; then
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
else
    log_info "Manteniendo Swarm (--keep-swarm o modo selectivo)"
fi

# ============================================================================
# PASO 4: Eliminar volúmenes de DistriSearch
# ============================================================================
if [ "$KEEP_VOLUMES" != true ] && [ "$SERVICES_ONLY" != true ] && [ "$NETWORKS_ONLY" != true ]; then
    log_step "Eliminando volúmenes de datos..."
    
    # Patrones de volúmenes a eliminar (incluyendo el prefijo configurable)
    VOLUME_PATTERNS="node[0-9]|slave[0-9]|master-|coordinator-|${SERVICE_PREFIX}|mongodb|redis"
    
    VOLUMES=$(docker volume ls --format "{{.Name}}" 2>/dev/null | grep -E "$VOLUME_PATTERNS" || true)
    
    if [ -n "$VOLUMES" ]; then
        echo "$VOLUMES" | while read vol; do
            docker volume rm "$vol" 2>/dev/null && echo "  ✓ Eliminado volumen: $vol" || echo "  ⚠ No se pudo eliminar: $vol"
        done
    else
        echo "  No hay volúmenes de DistriSearch"
    fi
    
    # Si solo queremos volúmenes, terminar aquí
    if [ "$VOLUMES_ONLY" = true ]; then
        log_info "Limpieza de volúmenes completada (modo --volumes-only)"
        exit 0
    fi
else
    log_info "Manteniendo volúmenes (--keep-volumes o modo selectivo)"
fi

# ============================================================================
# PASO 5: Eliminar redes de DistriSearch
# ============================================================================
if [ "$SERVICES_ONLY" != true ] && [ "$VOLUMES_ONLY" != true ]; then
    log_step "Eliminando redes..."
    
    NETWORKS=$(docker network ls --format "{{.Name}}" 2>/dev/null | grep -E "${SERVICE_PREFIX}" || true)
    
    if [ -n "$NETWORKS" ]; then
        echo "$NETWORKS" | while read net; do
            docker network rm "$net" 2>/dev/null && echo "  ✓ Eliminada red: $net" || echo "  ⚠ No se pudo eliminar: $net"
        done
    else
        echo "  No hay redes de DistriSearch"
    fi
    
    # Si solo queremos redes, terminar aquí
    if [ "$NETWORKS_ONLY" = true ]; then
        log_info "Limpieza de redes completada (modo --networks-only)"
        exit 0
    fi
fi

# ============================================================================
# PASO 6: Limpiar contenedores huérfanos
# ============================================================================
if [ "$VOLUMES_ONLY" != true ] && [ "$NETWORKS_ONLY" != true ]; then
    log_step "Limpiando contenedores huérfanos..."
    
    # Eliminar contenedores detenidos relacionados con DistriSearch
    CONTAINERS=$(docker ps -a --format "{{.Names}}" 2>/dev/null | grep -E "${SERVICE_PREFIX}|node|slave|master|coredns|load-balancer" || true)
    
    if [ -n "$CONTAINERS" ]; then
        echo "$CONTAINERS" | while read container; do
            docker rm -f "$container" 2>/dev/null && echo "  ✓ Eliminado contenedor: $container" || true
        done
    else
        echo "  No hay contenedores huérfanos"
    fi
fi

# ============================================================================
# PASO 7: Limpiar recursos Docker huérfanos (prune)
# ============================================================================
if [ "$SERVICES_ONLY" != true ]; then
    log_step "Limpiando recursos Docker huérfanos..."
    
    if [ "$KEEP_VOLUMES" != true ]; then
        echo "  Limpiando volúmenes no utilizados..."
        docker volume prune -f 2>/dev/null | grep -E "Total|deleted" || true
    fi
    
    echo "  Limpiando redes no utilizadas..."
    docker network prune -f 2>/dev/null | grep -E "Total|deleted" || true
    
    # Si se solicitó prune completo
    if [ "$DO_PRUNE" = true ]; then
        log_step "Ejecutando docker system prune (solicitado con --prune)..."
        docker system prune -f 2>/dev/null | grep -E "Total|deleted|reclaimed" || true
    fi
fi

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

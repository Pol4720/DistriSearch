#!/bin/bash
# ============================================================================
# 07-test-failover.sh - Probar failover automático del cluster HA
# ============================================================================
# Este script demuestra la elección automática de líder cuando el actual falla.
#
# Uso: ./07-test-failover.sh [--kill-leader] [--recover]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Test de Failover HA"
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

# ============================================================================
# Parsear argumentos
# ============================================================================
KILL_LEADER=false
RECOVER=false

for arg in "$@"; do
    case $arg in
        --kill-leader)
            KILL_LEADER=true
            ;;
        --recover)
            RECOVER=true
            ;;
    esac
done

# ============================================================================
# Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}')

# ============================================================================
# Función para obtener el líder actual
# ============================================================================
get_current_leader() {
    local DISTRISEARCH_NODES=$(docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-" | sort)
    
    for NODE in $DISTRISEARCH_NODES; do
        NODE_NUM=$(echo "$NODE" | grep -oE "[0-9]+$")
        API_PORT=$((8000 + NODE_NUM))
        
        # Verificar si este nodo es el líder
        IS_LEADER=$(curl -sf "http://$MANAGER_IP:$API_PORT/api/v1/cluster/status" --max-time 3 2>/dev/null | grep -oP '"is_leader"\s*:\s*\K(true|false)' || echo "false")
        
        if [ "$IS_LEADER" = "true" ]; then
            echo "$NODE"
            return 0
        fi
    done
    
    echo ""
    return 1
}

# ============================================================================
# Función para mostrar estado del cluster
# ============================================================================
show_cluster_state() {
    echo ""
    echo -e "${CYAN}Estado actual del cluster:${NC}"
    
    local DISTRISEARCH_NODES=$(docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-" | sort)
    
    for NODE in $DISTRISEARCH_NODES; do
        NODE_NUM=$(echo "$NODE" | grep -oE "[0-9]+$")
        API_PORT=$((8000 + NODE_NUM))
        
        # Estado del servicio
        REPLICAS=$(docker service ls --filter "name=$NODE" --format "{{.Replicas}}" 2>/dev/null)
        
        # Intentar obtener rol
        ROLE="unknown"
        IS_LEADER="false"
        if curl -sf "http://$MANAGER_IP:$API_PORT/api/v1/health" --max-time 2 &>/dev/null; then
            CLUSTER_STATUS=$(curl -sf "http://$MANAGER_IP:$API_PORT/api/v1/cluster/status" --max-time 3 2>/dev/null || echo "{}")
            ROLE=$(echo "$CLUSTER_STATUS" | grep -oP '"role"\s*:\s*"\K[^"]+' 2>/dev/null || echo "unknown")
            IS_LEADER=$(echo "$CLUSTER_STATUS" | grep -oP '"is_leader"\s*:\s*\K(true|false)' 2>/dev/null || echo "false")
        fi
        
        if [ "$IS_LEADER" = "true" ]; then
            echo -e "  $NODE: ${GREEN}LEADER ★${NC} (replicas: $REPLICAS)"
        elif [ "$REPLICAS" = "1/1" ]; then
            echo -e "  $NODE: ${CYAN}$ROLE${NC} (replicas: $REPLICAS)"
        else
            echo -e "  $NODE: ${YELLOW}$ROLE${NC} (replicas: $REPLICAS)"
        fi
    done
    echo ""
}

# ============================================================================
# Modo: Mostrar estado
# ============================================================================
if [ "$KILL_LEADER" = false ] && [ "$RECOVER" = false ]; then
    echo ""
    echo -e "${BLUE}Uso del script:${NC}"
    echo "  ./07-test-failover.sh                # Mostrar estado actual"
    echo "  ./07-test-failover.sh --kill-leader  # Simular fallo del líder"
    echo "  ./07-test-failover.sh --recover      # Recuperar nodo caído"
    echo ""
    
    show_cluster_state
    
    LEADER=$(get_current_leader)
    if [ -n "$LEADER" ]; then
        echo -e "${GREEN}Líder actual: $LEADER${NC}"
        echo ""
        echo "Para probar el failover, ejecuta:"
        echo "  ./07-test-failover.sh --kill-leader"
    else
        echo -e "${YELLOW}No se detectó un líder. El cluster puede estar eligiendo uno.${NC}"
    fi
    exit 0
fi

# ============================================================================
# Modo: Kill Leader
# ============================================================================
if [ "$KILL_LEADER" = true ]; then
    echo ""
    log_info "Obteniendo líder actual..."
    
    show_cluster_state
    
    LEADER=$(get_current_leader)
    
    if [ -z "$LEADER" ]; then
        log_error "No se encontró un líder activo"
        exit 1
    fi
    
    echo -e "${YELLOW}Líder actual: $LEADER${NC}"
    echo ""
    
    read -p "¿Deseas simular el fallo del líder ($LEADER)? (s/n): " confirm
    if [ "$confirm" != "s" ]; then
        echo "Cancelado"
        exit 0
    fi
    
    # Escalar a 0 para simular fallo
    log_info "Simulando fallo del líder..."
    docker service scale "$LEADER=0" --detach=false
    
    echo ""
    log_info "Líder detenido. Esperando elección de nuevo líder..."
    echo ""
    
    # Esperar a que Bully elija nuevo líder
    for i in {1..10}; do
        sleep 3
        echo -n "."
        NEW_LEADER=$(get_current_leader)
        if [ -n "$NEW_LEADER" ] && [ "$NEW_LEADER" != "$LEADER" ]; then
            echo ""
            echo -e "${GREEN}¡Nuevo líder elegido!${NC}"
            break
        fi
    done
    
    echo ""
    show_cluster_state
    
    NEW_LEADER=$(get_current_leader)
    if [ -n "$NEW_LEADER" ]; then
        echo -e "${GREEN}✓ Failover exitoso: $NEW_LEADER es el nuevo líder${NC}"
    else
        echo -e "${YELLOW}⚠ El cluster todavía está eligiendo líder${NC}"
    fi
    
    echo ""
    echo "Para recuperar el nodo caído, ejecuta:"
    echo "  ./07-test-failover.sh --recover"
    echo ""
fi

# ============================================================================
# Modo: Recover
# ============================================================================
if [ "$RECOVER" = true ]; then
    echo ""
    log_info "Buscando nodos caídos para recuperar..."
    
    DISTRISEARCH_NODES=$(docker service ls --format "{{.Name}}" | grep -E "^distrisearch-node-" | sort)
    
    RECOVERED=0
    for NODE in $DISTRISEARCH_NODES; do
        REPLICAS=$(docker service ls --filter "name=$NODE" --format "{{.Replicas}}" 2>/dev/null)
        
        if [ "$REPLICAS" = "0/1" ]; then
            log_info "Recuperando $NODE..."
            docker service scale "$NODE=1" --detach=false
            RECOVERED=$((RECOVERED + 1))
        fi
    done
    
    if [ $RECOVERED -eq 0 ]; then
        log_info "No hay nodos caídos para recuperar"
    else
        log_info "Recuperados $RECOVERED nodo(s)"
        echo ""
        log_info "Esperando a que el cluster se estabilice..."
        sleep 10
    fi
    
    show_cluster_state
    
    LEADER=$(get_current_leader)
    if [ -n "$LEADER" ]; then
        echo -e "${GREEN}Líder actual: $LEADER${NC}"
    fi
    echo ""
fi

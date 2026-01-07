#!/bin/bash
# ============================================================================
# 03-join-swarm.sh - Une un nodo worker al cluster Swarm
# ============================================================================
# Ejecutar en cada máquina WORKER
# Uso: ./03-join-swarm.sh <MANAGER_IP> <TOKEN>
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Unir Nodo al Swarm"
echo "=============================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# 1. Obtener parámetros
# ============================================================================
MANAGER_IP=$1
TOKEN=$2

if [ -z "$MANAGER_IP" ] || [ -z "$TOKEN" ]; then
    echo "Uso: $0 <MANAGER_IP> <TOKEN>"
    echo ""
    echo "Ejemplo:"
    echo "  $0 192.168.1.10 SWMTKN-1-xxx..."
    echo ""
    echo "El token y la IP te los proporciona el manager al ejecutar 02-init-swarm.sh"
    exit 1
fi

# ============================================================================
# 2. Verificar Docker
# ============================================================================
if ! docker info &> /dev/null; then
    log_error "Docker no está funcionando. Ejecuta primero 01-prepare-node.sh"
    exit 1
fi

# ============================================================================
# 3. Verificar conectividad con el manager
# ============================================================================
log_info "Verificando conectividad con el manager ($MANAGER_IP)..."

if ! ping -c 1 -W 3 $MANAGER_IP &> /dev/null; then
    log_error "No se puede conectar con el manager en $MANAGER_IP"
    echo "Verifica:"
    echo "  - Que el manager está encendido"
    echo "  - Que ambas máquinas están en la misma red"
    echo "  - Que el firewall permite la conexión"
    exit 1
fi

log_info "Conectividad OK"

# ============================================================================
# 4. Configurar firewall para Docker Swarm Routing Mesh
# ============================================================================
log_info "Configurando firewall para Docker Swarm..."

configure_firewall() {
    # Puertos requeridos para Docker Swarm
    # 2377/tcp - Cluster management
    # 7946/tcp+udp - Node communication  
    # 4789/udp - Overlay network (VXLAN)
    # Puertos de la aplicación
    # 8001 - Master API
    # 8081-8089 - Slave HTTP
    # 4431-4439 - Slave HTTPS
    # 8002-8009 - Slave API
    
    # Detectar si usamos ufw o iptables
    if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
        log_info "Configurando UFW..."
        ufw allow 2377/tcp comment "Docker Swarm management" 2>/dev/null || true
        ufw allow 7946/tcp comment "Docker Swarm node communication" 2>/dev/null || true
        ufw allow 7946/udp comment "Docker Swarm node communication" 2>/dev/null || true
        ufw allow 4789/udp comment "Docker Swarm overlay network VXLAN" 2>/dev/null || true
        ufw allow 8001/tcp comment "DistriSearch Master API" 2>/dev/null || true
        ufw allow 8081:8089/tcp comment "DistriSearch Slave HTTP" 2>/dev/null || true
        ufw allow 4431:4439/tcp comment "DistriSearch Slave HTTPS" 2>/dev/null || true
        ufw allow 8002:8009/tcp comment "DistriSearch Slave API" 2>/dev/null || true
        ufw reload 2>/dev/null || true
    else
        log_info "Configurando iptables..."
        # Docker Swarm ports
        iptables -A INPUT -p tcp --dport 2377 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p tcp --dport 7946 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p udp --dport 7946 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p udp --dport 4789 -j ACCEPT 2>/dev/null || true
        # Application ports
        iptables -A INPUT -p tcp --dport 8001 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p tcp --dport 8081:8089 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p tcp --dport 4431:4439 -j ACCEPT 2>/dev/null || true
        iptables -A INPUT -p tcp --dport 8002:8009 -j ACCEPT 2>/dev/null || true
        
        # Guardar reglas si es posible
        if command -v iptables-save &> /dev/null; then
            iptables-save > /etc/iptables.rules 2>/dev/null || true
        fi
    fi
    
    log_info "Firewall configurado para Docker Swarm"
}

configure_firewall

# ============================================================================
# 5. Verificar puerto Swarm
# ============================================================================
log_info "Verificando puerto Swarm (2377)..."

if nc -z -w3 $MANAGER_IP 2377 2>/dev/null; then
    log_info "Puerto 2377 accesible"
else
    log_warn "No se puede verificar el puerto 2377 (nc no instalado o puerto bloqueado)"
    log_warn "Continuando de todos modos..."
fi

# ============================================================================
# 6. Verificar estado actual
# ============================================================================
SWARM_STATUS=$(docker info --format '{{.Swarm.LocalNodeState}}')
if [ "$SWARM_STATUS" == "active" ]; then
    log_warn "Este nodo ya es parte de un Swarm"
    read -p "¿Deseas abandonar el Swarm actual y unirte al nuevo? (s/n): " confirm
    if [ "$confirm" == "s" ]; then
        docker swarm leave --force
    else
        exit 0
    fi
fi

# ============================================================================
# 7. Unirse al Swarm
# ============================================================================
log_info "Uniendo nodo al Swarm..."

docker swarm join --token $TOKEN $MANAGER_IP:2377

# ============================================================================
# 8. Verificar
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Nodo Unido al Swarm Correctamente${NC}"
echo "=============================================="
echo ""
log_info "Estado local del nodo:"
docker info --format 'Swarm: {{.Swarm.LocalNodeState}}'
docker info --format 'Manager: {{.Swarm.ControlAvailable}}'
docker info --format 'NodeID: {{.Swarm.NodeID}}'
echo ""
echo "Próximos pasos:"
echo "  1. Repetir este proceso en todos los workers"
echo "  2. En el MANAGER, verificar con: docker node ls"
echo "  3. En el MANAGER, ejecutar 05-deploy-master.sh"

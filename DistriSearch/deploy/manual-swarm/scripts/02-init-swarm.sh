#!/bin/bash
# ============================================================================
# 02-init-swarm.sh - Inicializa Docker Swarm en el nodo Manager
# ============================================================================
# Ejecutar SOLO en la máquina que será el MANAGER principal
# Uso: ./02-init-swarm.sh [IP_DEL_MANAGER]
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Inicializar Docker Swarm"
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
# 1. Obtener IP del manager
# ============================================================================
MANAGER_IP=$1

if [ -z "$MANAGER_IP" ]; then
    # Intentar detectar IP automáticamente
    MANAGER_IP=$(hostname -I | awk '{print $1}')
    log_warn "IP no especificada. Usando IP detectada: $MANAGER_IP"
    read -p "¿Es correcta esta IP? (s/n): " confirm
    if [ "$confirm" != "s" ]; then
        echo "Uso: $0 <IP_DEL_MANAGER>"
        echo "Ejemplo: $0 192.168.1.10"
        exit 1
    fi
fi

log_info "Usando IP del Manager: $MANAGER_IP"

# ============================================================================
# 2. Verificar que Docker está funcionando
# ============================================================================
if ! docker info &> /dev/null; then
    log_error "Docker no está funcionando. Ejecuta primero 01-prepare-node.sh"
    exit 1
fi

# ============================================================================
# 3. Verificar que no estamos ya en un Swarm
# ============================================================================
SWARM_STATUS=$(docker info --format '{{.Swarm.LocalNodeState}}')
if [ "$SWARM_STATUS" == "active" ]; then
    log_warn "Este nodo ya es parte de un Swarm"
    docker node ls
    echo ""
    read -p "¿Deseas reinicializar? Esto destruirá el cluster actual (s/n): " confirm
    if [ "$confirm" == "s" ]; then
        log_info "Abandonando Swarm actual..."
        docker swarm leave --force
    else
        exit 0
    fi
fi

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
        ufw allow 2377/tcp comment "Docker Swarm management"
        ufw allow 7946/tcp comment "Docker Swarm node communication"
        ufw allow 7946/udp comment "Docker Swarm node communication"
        ufw allow 4789/udp comment "Docker Swarm overlay network VXLAN"
        ufw allow 8001/tcp comment "DistriSearch Master API"
        ufw allow 8081:8089/tcp comment "DistriSearch Slave HTTP"
        ufw allow 4431:4439/tcp comment "DistriSearch Slave HTTPS"
        ufw allow 8002:8009/tcp comment "DistriSearch Slave API"
        ufw reload
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
# 5. Inicializar Swarm
# ============================================================================
log_info "Inicializando Docker Swarm..."

docker swarm init --advertise-addr $MANAGER_IP

# ============================================================================
# 6. Crear red overlay
# ============================================================================
log_info "Creando red overlay para DistriSearch..."

# Verificar si la red ya existe
if docker network ls | grep -q "distrisearch-network"; then
    log_warn "Red distrisearch-network ya existe"
else
    docker network create \
        --driver overlay \
        --attachable \
        --subnet 10.0.10.0/24 \
        distrisearch-network
    log_info "Red overlay creada: distrisearch-network (10.0.10.0/24)"
fi

# ============================================================================
# 7. Guardar tokens
# ============================================================================
log_info "Guardando tokens de acceso..."

WORKER_TOKEN=$(docker swarm join-token -q worker)
MANAGER_TOKEN=$(docker swarm join-token -q manager)

mkdir -p /opt/distrisearch/config

cat > /opt/distrisearch/config/swarm-tokens.env << EOF
# Tokens de Docker Swarm - MANTENER SEGURO
# Generado: $(date)
# Manager: $MANAGER_IP

SWARM_MANAGER_IP=$MANAGER_IP
SWARM_WORKER_TOKEN=$WORKER_TOKEN
SWARM_MANAGER_TOKEN=$MANAGER_TOKEN

# Comando para unir WORKERS:
# docker swarm join --token $WORKER_TOKEN $MANAGER_IP:2377

# Comando para unir MANAGERS adicionales:
# docker swarm join --token $MANAGER_TOKEN $MANAGER_IP:2377
EOF

chmod 600 /opt/distrisearch/config/swarm-tokens.env

# ============================================================================
# 8. Mostrar información
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Swarm Inicializado Correctamente${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}Para unir WORKERS al cluster, ejecuta en cada worker:${NC}"
echo ""
echo -e "${YELLOW}docker swarm join --token $WORKER_TOKEN $MANAGER_IP:2377${NC}"
echo ""
echo "=============================================="
echo ""

# Mostrar estado
log_info "Estado actual del cluster:"
docker node ls

echo ""
log_info "Tokens guardados en: /opt/distrisearch/config/swarm-tokens.env"
echo ""
echo "Próximos pasos:"
echo "  1. Copiar el comando 'docker swarm join' a los workers"
echo "  2. En cada worker: ejecutar 03-join-swarm.sh o el comando directamente"
echo "  3. Volver aquí y ejecutar 05-deploy-master.sh"

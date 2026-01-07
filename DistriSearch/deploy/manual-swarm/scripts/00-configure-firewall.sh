#!/bin/bash
# ============================================================================
# 00-configure-firewall.sh - Configura el firewall para Docker Swarm
# ============================================================================
# Ejecutar en TODOS los nodos (manager y workers) si hay problemas de red
# Uso: sudo ./00-configure-firewall.sh
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Configurar Firewall"
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
# Verificar que somos root
# ============================================================================
if [ "$EUID" -ne 0 ]; then
    log_error "Este script debe ejecutarse como root (sudo)"
    exit 1
fi

# ============================================================================
# Puertos requeridos
# ============================================================================
echo ""
echo -e "${BLUE}Puertos que se configurarán:${NC}"
echo ""
echo "  Docker Swarm:"
echo "    - 2377/tcp  : Gestión del cluster"
echo "    - 7946/tcp  : Comunicación entre nodos"
echo "    - 7946/udp  : Comunicación entre nodos"
echo "    - 4789/udp  : Red overlay (VXLAN) - CRÍTICO para routing mesh"
echo ""
echo "  DistriSearch:"
echo "    - 8001/tcp  : Master API"
echo "    - 8081-8089 : Slave HTTP (Frontend)"
echo "    - 4431-4439 : Slave HTTPS (Frontend)"
echo "    - 8002-8009 : Slave API (Backend)"
echo ""

# ============================================================================
# Configurar según el tipo de firewall
# ============================================================================

configure_ufw() {
    log_info "Configurando UFW..."
    
    # Docker Swarm
    ufw allow 2377/tcp comment "Docker Swarm management"
    ufw allow 7946/tcp comment "Docker Swarm node communication"
    ufw allow 7946/udp comment "Docker Swarm node communication"
    ufw allow 4789/udp comment "Docker Swarm overlay network VXLAN"
    
    # DistriSearch
    ufw allow 8001/tcp comment "DistriSearch Master API"
    ufw allow 8081:8089/tcp comment "DistriSearch Slave HTTP"
    ufw allow 4431:4439/tcp comment "DistriSearch Slave HTTPS"
    ufw allow 8002:8009/tcp comment "DistriSearch Slave API"
    
    # MongoDB y Redis (solo red interna)
    ufw allow from 10.0.0.0/8 to any port 27017 comment "MongoDB internal"
    ufw allow from 172.16.0.0/12 to any port 27017 comment "MongoDB internal"
    ufw allow from 192.168.0.0/16 to any port 27017 comment "MongoDB internal"
    ufw allow from 10.0.0.0/8 to any port 6379 comment "Redis internal"
    ufw allow from 172.16.0.0/12 to any port 6379 comment "Redis internal"
    ufw allow from 192.168.0.0/16 to any port 6379 comment "Redis internal"
    
    ufw --force reload
    log_info "UFW configurado correctamente"
}

configure_iptables() {
    log_info "Configurando iptables..."
    
    # Docker Swarm
    iptables -I INPUT -p tcp --dport 2377 -j ACCEPT
    iptables -I INPUT -p tcp --dport 7946 -j ACCEPT
    iptables -I INPUT -p udp --dport 7946 -j ACCEPT
    iptables -I INPUT -p udp --dport 4789 -j ACCEPT
    
    # DistriSearch
    iptables -I INPUT -p tcp --dport 8001 -j ACCEPT
    iptables -I INPUT -p tcp -m multiport --dports 8081:8089 -j ACCEPT
    iptables -I INPUT -p tcp -m multiport --dports 4431:4439 -j ACCEPT
    iptables -I INPUT -p tcp -m multiport --dports 8002:8009 -j ACCEPT
    
    # Guardar reglas
    if command -v iptables-save &> /dev/null; then
        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4
        log_info "Reglas guardadas en /etc/iptables/rules.v4"
    fi
    
    log_info "iptables configurado correctamente"
}

configure_firewalld() {
    log_info "Configurando firewalld..."
    
    # Docker Swarm
    firewall-cmd --permanent --add-port=2377/tcp
    firewall-cmd --permanent --add-port=7946/tcp
    firewall-cmd --permanent --add-port=7946/udp
    firewall-cmd --permanent --add-port=4789/udp
    
    # DistriSearch
    firewall-cmd --permanent --add-port=8001/tcp
    firewall-cmd --permanent --add-port=8081-8089/tcp
    firewall-cmd --permanent --add-port=4431-4439/tcp
    firewall-cmd --permanent --add-port=8002-8009/tcp
    
    firewall-cmd --reload
    log_info "firewalld configurado correctamente"
}

# Detectar y configurar
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    if echo "$UFW_STATUS" | grep -q "active"; then
        configure_ufw
    elif echo "$UFW_STATUS" | grep -q "inactive"; then
        log_warn "UFW está instalado pero inactivo"
        read -p "¿Deseas activar UFW? (s/n): " confirm
        if [ "$confirm" == "s" ]; then
            ufw --force enable
            configure_ufw
        else
            log_info "Configurando iptables en su lugar..."
            configure_iptables
        fi
    else
        configure_iptables
    fi
elif command -v firewall-cmd &> /dev/null; then
    configure_firewalld
else
    configure_iptables
fi

# ============================================================================
# Verificar configuración
# ============================================================================
echo ""
log_info "Verificando puertos..."
echo ""

check_port() {
    local PORT=$1
    local DESC=$2
    if ss -tlnp | grep -q ":$PORT " 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Puerto $PORT ($DESC) - Escuchando"
    else
        echo -e "  ${YELLOW}○${NC} Puerto $PORT ($DESC) - No hay servicio escuchando (normal si no está desplegado)"
    fi
}

check_port 2377 "Swarm Management"
check_port 8001 "Master API"
check_port 8081 "Slave HTTP"
check_port 8002 "Slave API"

echo ""
echo "=============================================="
echo -e "${GREEN}  Firewall Configurado${NC}"
echo "=============================================="
echo ""
echo "IMPORTANTE: Ejecuta este script en TODOS los nodos del cluster"
echo ""
echo "Si sigues teniendo problemas de routing mesh:"
echo "  1. Reinicia Docker en todos los nodos: sudo systemctl restart docker"
echo "  2. Verifica la red overlay: docker network inspect distrisearch-network"
echo "  3. Prueba conectividad UDP: nc -zuv <otro-nodo> 4789"
echo ""

#!/bin/bash
# ============================================================================
# 01-prepare-node.sh - Prepara una máquina Linux para el cluster
# ============================================================================
# Ejecutar en CADA máquina del cluster
# Uso: sudo ./01-prepare-node.sh
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Preparación de Nodo"
echo "=============================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1 (ya existe)"; }

# ============================================================================
# 1. Verificar que se ejecuta como root
# ============================================================================
if [ "$EUID" -ne 0 ]; then
    log_error "Este script debe ejecutarse como root (sudo)"
    exit 1
fi

# ============================================================================
# 2. Actualizar sistema (solo si no se ha hecho recientemente)
# ============================================================================
LAST_UPDATE=$(stat -c %Y /var/lib/apt/lists/partial 2>/dev/null || echo "0")
CURRENT_TIME=$(date +%s)
DIFF=$((CURRENT_TIME - LAST_UPDATE))

if [ "$DIFF" -gt 86400 ]; then  # Más de 24 horas
    log_info "Actualizando sistema..."
    apt-get update -qq
    apt-get upgrade -y -qq
else
    log_skip "Sistema actualizado recientemente"
fi

# ============================================================================
# 3. Instalar Docker
# ============================================================================
if command -v docker &> /dev/null; then
    log_skip "Docker ya instalado: $(docker --version)"
    # Verificar que el servicio está corriendo
    if ! systemctl is-active --quiet docker; then
        log_info "Iniciando servicio Docker..."
        systemctl start docker
    fi
else
    log_info "Instalando Docker..."
    apt-get install -y -qq docker.io
    systemctl enable docker
    systemctl start docker
    log_info "Docker instalado: $(docker --version)"
fi

# ============================================================================
# 4. Añadir usuario al grupo docker
# ============================================================================
CURRENT_USER=${SUDO_USER:-$USER}
if groups $CURRENT_USER | grep -q docker; then
    log_info "Usuario $CURRENT_USER ya está en grupo docker"
else
    log_info "Añadiendo $CURRENT_USER al grupo docker..."
    usermod -aG docker $CURRENT_USER
    log_warn "Debes cerrar sesión y volver a entrar para que los cambios surtan efecto"
fi

# ============================================================================
# 5. Configurar firewall
# ============================================================================
log_info "Configurando firewall..."

# Verificar si ufw está instalado
if command -v ufw &> /dev/null; then
    # Verificar si ya se configuraron los puertos de DistriSearch
    if ufw status | grep -q "Docker Swarm management"; then
        log_skip "Firewall ya configurado para DistriSearch"
    else
        # Puertos para Docker Swarm
        ufw allow 2377/tcp comment 'Docker Swarm management'
        ufw allow 7946/tcp comment 'Docker Swarm node communication'
        ufw allow 7946/udp comment 'Docker Swarm node communication'
        ufw allow 4789/udp comment 'Docker Swarm overlay network'
        
        # Puertos para DistriSearch
        ufw allow 8443/tcp comment 'DistriSearch HTTPS'
        ufw allow 80/tcp comment 'DistriSearch HTTP'
        ufw allow 443/tcp comment 'DistriSearch HTTPS Frontend'
        ufw allow 8000:8010/tcp comment 'DistriSearch API'
        ufw allow 27017/tcp comment 'MongoDB'
        
        # Habilitar firewall si no está activo
        if ufw status | grep -q "inactive"; then
            ufw --force enable
        fi
        
        ufw reload
        log_info "Firewall configurado"
    fi
else
    log_warn "UFW no instalado. Configura el firewall manualmente."
fi

# ============================================================================
# 6. Configurar límites del sistema
# ============================================================================
# Verificar si ya se configuraron los límites
if grep -q "DistriSearch limits" /etc/security/limits.conf 2>/dev/null; then
    log_skip "Límites del sistema ya configurados"
else
    log_info "Configurando límites del sistema..."
    
    # Aumentar límites de archivos abiertos
    cat >> /etc/security/limits.conf << 'EOF'
# DistriSearch limits
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535
EOF
fi

# Verificar si ya se configuró sysctl
if grep -q "DistriSearch network tuning" /etc/sysctl.conf 2>/dev/null; then
    log_skip "Configuración sysctl ya aplicada"
else
    # Configurar sysctl para mejor rendimiento de red
    cat >> /etc/sysctl.conf << 'EOF'
# DistriSearch network tuning
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
vm.overcommit_memory = 1
EOF
    sysctl -p
fi

# ============================================================================
# 7. Crear directorios necesarios
# ============================================================================
if [ -d "/opt/distrisearch" ]; then
    log_skip "Directorio /opt/distrisearch ya existe"
else
    log_info "Creando directorios..."
    mkdir -p /opt/distrisearch/data
    mkdir -p /opt/distrisearch/logs
    mkdir -p /opt/distrisearch/config
    chmod 755 /opt/distrisearch
fi

# ============================================================================
# 8. Verificar instalación
# ============================================================================
echo ""
echo "=============================================="
echo "  Verificación de Instalación"
echo "=============================================="

echo -n "Docker: "
if docker info &> /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FALLO${NC}"
fi

echo -n "Firewall: "
if ufw status | grep -q "active"; then
    echo -e "${GREEN}Activo${NC}"
else
    echo -e "${YELLOW}Inactivo${NC}"
fi

echo ""
log_info "Preparación completada!"
log_warn "Si añadiste usuario al grupo docker, cierra sesión y vuelve a entrar"
echo ""
echo "Próximo paso:"
echo "  - En el MANAGER: ejecutar 02-init-swarm.sh"
echo "  - En los WORKERS: esperar token y ejecutar 03-join-swarm.sh"

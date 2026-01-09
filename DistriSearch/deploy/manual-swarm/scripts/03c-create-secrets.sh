#!/bin/bash
# ============================================================================
# 03c-create-secrets.sh - Crear Docker Secrets para el cluster
# ============================================================================
# Este script crea los secrets necesarios antes de desplegar servicios.
# Debe ejecutarse ANTES de 04-deploy-infrastructure-ha.sh
#
# Secrets creados:
#   - tls-cert: Certificado SSL/TLS para HTTPS
#   - tls-key: Clave privada del certificado
#   - jwt-secret: Secret para firmar tokens JWT (opcional)
#
# Ejecutar SOLO en el MANAGER
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Crear Docker Secrets"
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
log_skip() { echo -e "${CYAN}[SKIP]${NC} $1 (ya existe)"; }

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

log_info "Nodo Manager confirmado"

# Obtener directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CERTS_DIR="$SCRIPT_DIR/../certs"

# ============================================================================
# 2. Crear directorio para certificados si no existe
# ============================================================================
mkdir -p "$CERTS_DIR"

# ============================================================================
# 3. Generar certificados TLS si no existen
# ============================================================================
CERT_FILE="$CERTS_DIR/server.crt"
KEY_FILE="$CERTS_DIR/server.key"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    log_info "Certificados existentes encontrados en $CERTS_DIR"
else
    log_info "Generando certificados TLS auto-firmados..."
    
    # Obtener IP del manager para el certificado
    MANAGER_IP=$(hostname -I | awk '{print $1}')
    
    # Generar certificado auto-firmado válido por 365 días
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/C=ES/ST=State/L=City/O=DistriSearch/OU=Development/CN=distrisearch.local" \
        -addext "subjectAltName=DNS:distrisearch.local,DNS:*.distrisearch.local,DNS:localhost,IP:127.0.0.1,IP:$MANAGER_IP"
    
    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"
    
    log_info "Certificados generados:"
    log_info "  - Certificado: $CERT_FILE"
    log_info "  - Clave: $KEY_FILE"
fi

# ============================================================================
# 4. Crear/Actualizar Docker Secrets
# ============================================================================
echo ""
log_info "Creando Docker Secrets..."

# Función para crear secret si no existe
create_secret_safe() {
    local name=$1
    local file=$2
    
    if docker secret inspect "$name" &>/dev/null; then
        log_skip "Secret $name"
    else
        docker secret create "$name" "$file"
        log_info "Secret '$name' creado"
    fi
}

# Crear secrets de TLS
create_secret_safe "tls-cert" "$CERT_FILE"
create_secret_safe "tls-key" "$KEY_FILE"

# ============================================================================
# 5. Crear JWT Secret (para sesiones compartidas entre nodos)
# ============================================================================
JWT_SECRET_FILE="$CERTS_DIR/jwt-secret"

if [ ! -f "$JWT_SECRET_FILE" ]; then
    # Generar un secret aleatorio seguro
    openssl rand -base64 64 | tr -d '\n' > "$JWT_SECRET_FILE"
    chmod 600 "$JWT_SECRET_FILE"
    log_info "JWT secret generado"
fi

if docker secret inspect "jwt-secret" &>/dev/null; then
    log_skip "Secret jwt-secret"
else
    docker secret create "jwt-secret" "$JWT_SECRET_FILE"
    log_info "Secret 'jwt-secret' creado"
fi

# ============================================================================
# 6. Verificar secrets creados
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Secrets Creados${NC}"
echo "=============================================="
echo ""
docker secret ls
echo ""

log_info "Los secrets están listos para usar en los servicios."
echo ""
echo -e "${CYAN}Archivos de respaldo guardados en:${NC}"
echo "  $CERTS_DIR/"
ls -la "$CERTS_DIR/"
echo ""
echo -e "${YELLOW}IMPORTANTE:${NC} Guarda los archivos de $CERTS_DIR en un lugar seguro."
echo "Si se pierden los secrets del swarm, puedes recrearlos con este script."
echo ""
echo "Próximo paso:"
echo "  ./04-deploy-infrastructure-ha.sh"
echo ""

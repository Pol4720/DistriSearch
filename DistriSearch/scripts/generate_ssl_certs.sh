#!/bin/bash
# Script para generar certificados SSL autofirmados para DistriSearch
# Uso: ./generate_ssl_certs.sh [hostname-o-ip]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Parámetros
HOSTNAME="${1:-localhost}"
OUTPUT_DIR="../certs"

echo -e "${CYAN}=== Generador de Certificados SSL para DistriSearch ===${NC}"
echo ""

# Crear directorio para certificados
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/$OUTPUT_DIR"

if [ ! -d "$CERT_DIR" ]; then
    mkdir -p "$CERT_DIR"
    echo -e "${GREEN}[✓] Directorio de certificados creado: $CERT_DIR${NC}"
fi

# Obtener la IP de la máquina (LAN)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
else
    # Linux
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

echo -e "${YELLOW}[i] IP Local detectada: $LOCAL_IP${NC}"
echo -e "${YELLOW}[i] Hostname: $HOSTNAME${NC}"
echo ""

# Rutas de certificados
CERT_PATH="$CERT_DIR/distrisearch.crt"
KEY_PATH="$CERT_DIR/distrisearch.key"
PEM_PATH="$CERT_DIR/distrisearch.pem"
CONFIG_PATH="$CERT_DIR/openssl.cnf"

# Verificar si OpenSSL está disponible
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}[!] OpenSSL no encontrado.${NC}"
    echo ""
    echo -e "${CYAN}Por favor, instala OpenSSL:${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${WHITE}  macOS: brew install openssl${NC}"
    elif [[ -f /etc/debian_version ]]; then
        echo -e "${WHITE}  Debian/Ubuntu: sudo apt-get install openssl${NC}"
    elif [[ -f /etc/redhat-release ]]; then
        echo -e "${WHITE}  RedHat/CentOS: sudo yum install openssl${NC}"
    else
        echo -e "${WHITE}  Consulta la documentación de tu distribución${NC}"
    fi
    exit 1
fi

echo -e "${GREEN}[✓] OpenSSL encontrado: $(which openssl)${NC}"
echo ""

# Crear configuración de OpenSSL con SANs
cat > "$CONFIG_PATH" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C=ES
ST=State
L=City
O=DistriSearch
OU=Development
CN=$HOSTNAME

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $HOSTNAME
DNS.2 = localhost
DNS.3 = backend
DNS.4 = *.local
IP.1 = 127.0.0.1
IP.2 = $LOCAL_IP
EOF

echo -e "${GREEN}[✓] Configuración de OpenSSL creada${NC}"

# Generar certificado
echo -e "${YELLOW}[i] Generando certificado autofirmado...${NC}"

if openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$KEY_PATH" \
    -out "$CERT_PATH" \
    -days 365 \
    -config "$CONFIG_PATH" \
    -extensions v3_req &> /dev/null; then
    
    echo -e "${GREEN}[✓] Certificado generado exitosamente${NC}"
    
    # Crear archivo PEM combinado
    cat "$KEY_PATH" "$CERT_PATH" > "$PEM_PATH"
    echo -e "${GREEN}[✓] Archivo PEM combinado creado${NC}"
    
    echo ""
    echo -e "${GREEN}=== Certificados generados ===${NC}"
    echo -e "${WHITE}Certificado: $CERT_PATH${NC}"
    echo -e "${WHITE}Clave privada: $KEY_PATH${NC}"
    echo -e "${WHITE}PEM combinado: $PEM_PATH${NC}"
    echo ""
    echo -e "${YELLOW}[i] Los certificados son válidos por 365 días${NC}"
    echo -e "${YELLOW}[!] IMPORTANTE: Estos son certificados autofirmados para desarrollo.${NC}"
    echo -e "${YELLOW}[!] Los navegadores mostrarán una advertencia de seguridad.${NC}"
    echo ""
    echo -e "${CYAN}=== Próximos pasos ===${NC}"
    echo -e "${WHITE}1. Configura las variables de entorno en .env:${NC}"
    echo -e "${GRAY}   SSL_CERT_FILE=$CERT_PATH${NC}"
    echo -e "${GRAY}   SSL_KEY_FILE=$KEY_PATH${NC}"
    echo -e "${GRAY}   ENABLE_SSL=true${NC}"
    echo ""
    echo -e "${WHITE}2. Para acceso desde red externa, configura también:${NC}"
    echo -e "${GRAY}   PUBLIC_URL=https://$LOCAL_IP:8000${NC}"
    echo -e "${GRAY}   EXTERNAL_IP=$LOCAL_IP${NC}"
    echo ""
    echo -e "${GREEN}[✓] Proceso completado exitosamente${NC}"
else
    echo -e "${RED}[✗] Error al generar certificados${NC}"
    exit 1
fi

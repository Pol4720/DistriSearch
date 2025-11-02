#!/bin/bash
# Script de Configuración Rápida de DistriSearch con HTTPS
# Uso: ./setup_https.sh [ip-opcional]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Parámetro opcional de IP
IP="${1:-}"

echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   DistriSearch - Configuración HTTPS Automatizada    ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Obtener IP si no se proporcionó
if [ -z "$IP" ]; then
    echo -e "${YELLOW}[i] Detectando tu IP local...${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1)
    else
        # Linux
        IP=$(hostname -I | awk '{print $1}')
    fi
    
    if [ -z "$IP" ]; then
        echo -e "${RED}[!] No se pudo detectar automáticamente la IP.${NC}"
        read -p "Por favor, ingresa tu IP manualmente (ejemplo: 192.168.1.100): " IP
    fi
fi

echo -e "${GREEN}[✓] IP detectada/configurada: $IP${NC}"
echo ""

# Verificar directorio
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$PROJECT_ROOT/backend" ]; then
    echo -e "${RED}[✗] Error: No se encuentra el directorio backend.${NC}"
    echo -e "${RED}    Asegúrate de ejecutar el script desde DistriSearch/scripts/${NC}"
    exit 1
fi

echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"
echo -e "${CYAN}PASO 1: Generar Certificados SSL${NC}"
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"

CERTS_PATH="$PROJECT_ROOT/certs"
CERT_FILE="$CERTS_PATH/distrisearch.crt"

if [ -f "$CERT_FILE" ]; then
    read -p "Los certificados ya existen. ¿Regenerar? (s/n): " response
    if [ "$response" = "s" ] || [ "$response" = "S" ]; then
        bash "$SCRIPT_DIR/generate_ssl_certs.sh" "$IP"
    else
        echo -e "${YELLOW}[i] Usando certificados existentes${NC}"
    fi
else
    bash "$SCRIPT_DIR/generate_ssl_certs.sh" "$IP"
fi

echo ""
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"
echo -e "${CYAN}PASO 2: Configurar Backend${NC}"
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"

BACKEND_ENV_PATH="$PROJECT_ROOT/backend/.env"
BACKEND_ENV_EXAMPLE="$PROJECT_ROOT/backend/.env.example"

SKIP_BACKEND=false
if [ -f "$BACKEND_ENV_PATH" ]; then
    read -p "El archivo backend/.env ya existe. ¿Sobrescribir? (s/n): " response
    if [ "$response" != "s" ] && [ "$response" != "S" ]; then
        echo -e "${YELLOW}[i] Manteniendo backend/.env existente${NC}"
        SKIP_BACKEND=true
    fi
fi

if [ "$SKIP_BACKEND" = false ]; then
    if [ -f "$BACKEND_ENV_EXAMPLE" ]; then
        cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV_PATH"
        
        # Actualizar valores en el .env
        sed -i.bak "s|PUBLIC_URL=.*|PUBLIC_URL=https://${IP}:8000|g" "$BACKEND_ENV_PATH"
        sed -i.bak "s|EXTERNAL_IP=.*|EXTERNAL_IP=$IP|g" "$BACKEND_ENV_PATH"
        sed -i.bak "s|ENABLE_SSL=.*|ENABLE_SSL=true|g" "$BACKEND_ENV_PATH"
        sed -i.bak "s|BACKEND_HOST=.*|BACKEND_HOST=0.0.0.0|g" "$BACKEND_ENV_PATH"
        rm -f "$BACKEND_ENV_PATH.bak"
        
        echo -e "${GREEN}[✓] Backend configurado con IP: $IP${NC}"
    else
        echo -e "${YELLOW}[!] Advertencia: No se encuentra .env.example del backend${NC}"
    fi
fi

echo ""
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"
echo -e "${CYAN}PASO 3: Configurar Frontend${NC}"
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"

FRONTEND_ENV_PATH="$PROJECT_ROOT/frontend/.env"
FRONTEND_ENV_EXAMPLE="$PROJECT_ROOT/frontend/.env.example"

SKIP_FRONTEND=false
if [ -f "$FRONTEND_ENV_PATH" ]; then
    read -p "El archivo frontend/.env ya existe. ¿Sobrescribir? (s/n): " response
    if [ "$response" != "s" ] && [ "$response" != "S" ]; then
        echo -e "${YELLOW}[i] Manteniendo frontend/.env existente${NC}"
        SKIP_FRONTEND=true
    fi
fi

if [ "$SKIP_FRONTEND" = false ]; then
    if [ -f "$FRONTEND_ENV_EXAMPLE" ]; then
        cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV_PATH"
        
        # Actualizar valores en el .env
        sed -i.bak "s|DISTRISEARCH_BACKEND_URL=.*|DISTRISEARCH_BACKEND_URL=https://${IP}:8000|g" "$FRONTEND_ENV_PATH"
        sed -i.bak "s|DISTRISEARCH_BACKEND_PUBLIC_URL=.*|DISTRISEARCH_BACKEND_PUBLIC_URL=https://${IP}:8000|g" "$FRONTEND_ENV_PATH"
        rm -f "$FRONTEND_ENV_PATH.bak"
        
        echo -e "${GREEN}[✓] Frontend configurado con IP: $IP${NC}"
    else
        echo -e "${YELLOW}[!] Advertencia: No se encuentra .env.example del frontend${NC}"
    fi
fi

echo ""
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"
echo -e "${CYAN}PASO 4: Configurar Firewall${NC}"
echo -e "${GRAY}─────────────────────────────────────────────────────────${NC}"

# Detectar sistema operativo y firewall
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}[i] macOS detectado${NC}"
    echo -e "${WHITE}Para habilitar el acceso en red, configura el firewall manualmente:${NC}"
    echo -e "${GRAY}  1. Ve a: Preferencias del Sistema > Seguridad y Privacidad > Firewall${NC}"
    echo -e "${GRAY}  2. Click en 'Opciones de Firewall'${NC}"
    echo -e "${GRAY}  3. Agrega Python a las aplicaciones permitidas${NC}"
elif command -v ufw &> /dev/null; then
    # Ubuntu/Debian con UFW
    echo -e "${YELLOW}[i] UFW detectado${NC}"
    
    if [ "$EUID" -eq 0 ]; then
        echo -e "${YELLOW}[i] Configurando reglas de firewall...${NC}"
        
        ufw allow 8000/tcp comment "DistriSearch Backend" &> /dev/null || true
        ufw allow 8501/tcp comment "DistriSearch Frontend" &> /dev/null || true
        
        echo -e "${GREEN}[✓] Reglas de firewall configuradas${NC}"
    else
        echo -e "${YELLOW}[!] No se ejecutó como root. Configura el firewall manualmente:${NC}"
        echo -e "${WHITE}  Ejecuta como root:${NC}"
        echo -e "${GRAY}    sudo ufw allow 8000/tcp${NC}"
        echo -e "${GRAY}    sudo ufw allow 8501/tcp${NC}"
    fi
elif command -v firewall-cmd &> /dev/null; then
    # RedHat/CentOS/Fedora con firewalld
    echo -e "${YELLOW}[i] firewalld detectado${NC}"
    
    if [ "$EUID" -eq 0 ]; then
        echo -e "${YELLOW}[i] Configurando reglas de firewall...${NC}"
        
        firewall-cmd --permanent --add-port=8000/tcp &> /dev/null || true
        firewall-cmd --permanent --add-port=8501/tcp &> /dev/null || true
        firewall-cmd --reload &> /dev/null || true
        
        echo -e "${GREEN}[✓] Reglas de firewall configuradas${NC}"
    else
        echo -e "${YELLOW}[!] No se ejecutó como root. Configura el firewall manualmente:${NC}"
        echo -e "${WHITE}  Ejecuta como root:${NC}"
        echo -e "${GRAY}    sudo firewall-cmd --permanent --add-port=8000/tcp${NC}"
        echo -e "${GRAY}    sudo firewall-cmd --permanent --add-port=8501/tcp${NC}"
        echo -e "${GRAY}    sudo firewall-cmd --reload${NC}"
    fi
else
    echo -e "${YELLOW}[i] No se detectó firewall o ya está deshabilitado${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}            ¡Configuración Completada!                ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${CYAN}📋 Resumen de Configuración:${NC}"
echo -e "${WHITE}  • IP: $IP${NC}"
echo -e "${WHITE}  • Certificados: $CERTS_PATH${NC}"
echo -e "${WHITE}  • Backend: https://${IP}:8000${NC}"
echo -e "${WHITE}  • Frontend: http://${IP}:8501${NC}"
echo ""

echo -e "${CYAN}🚀 Próximos Pasos:${NC}"
echo ""
echo -e "${YELLOW}1. Iniciar el Backend:${NC}"
echo -e "${GRAY}   cd $PROJECT_ROOT/backend${NC}"
echo -e "${GRAY}   python main.py${NC}"
echo ""
echo -e "${YELLOW}2. Iniciar el Frontend (en otra terminal):${NC}"
echo -e "${GRAY}   cd $PROJECT_ROOT/frontend${NC}"
echo -e "${GRAY}   streamlit run app.py${NC}"
echo ""
echo -e "${YELLOW}3. Acceder desde cualquier PC en la red:${NC}"
echo -e "${GRAY}   https://${IP}:8501${NC}"
echo -e "${GRAY}   (Acepta la advertencia del certificado autofirmado)${NC}"
echo ""

echo -e "${CYAN}📖 Documentación:${NC}"
echo -e "${WHITE}   docs/QUICKSTART_HTTPS.md - Guía rápida${NC}"
echo -e "${WHITE}   docs/HTTPS_SETUP.md - Configuración detallada${NC}"
echo -e "${WHITE}   docs/NETWORK_DOWNLOAD_FIX.md - Solución de problemas${NC}"
echo ""

read -p "¿Deseas abrir la documentación ahora? (s/n): " response
if [ "$response" = "s" ] || [ "$response" = "S" ]; then
    QUICKSTART_PATH="$PROJECT_ROOT/docs/QUICKSTART_HTTPS.md"
    if [ -f "$QUICKSTART_PATH" ]; then
        if command -v xdg-open &> /dev/null; then
            xdg-open "$QUICKSTART_PATH" &
        elif command -v open &> /dev/null; then
            open "$QUICKSTART_PATH" &
        else
            echo -e "${YELLOW}[i] Abre manualmente: $QUICKSTART_PATH${NC}"
        fi
    fi
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   ¡Gracias por usar DistriSearch! 🔍✨              ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"

#!/bin/bash
# ============================================================================
# GUÍA DE DESPLIEGUE LIMPIO - DistriSearch HA
# ============================================================================
# Este script guía paso a paso un despliegue completamente limpio.
# Incluye: limpieza, reconstrucción de imágenes, y despliegue de nodos.
#
# REQUISITOS PREVIOS:
# - Docker instalado en todas las máquinas
# - Las máquinas pueden comunicarse por red (ping funciona)
# - SSH configurado entre máquinas (opcional, para gestión remota)
#
# USO:
#   ./clean-deploy-guide.sh [--execute]
#
#   Sin argumentos: Muestra los pasos a ejecutar
#   --execute: Ejecuta los pasos automáticamente (CUIDADO: destructivo)
#
# ============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/../../docker"
EXECUTE_MODE=false

if [ "$1" = "--execute" ]; then
    EXECUTE_MODE=true
fi

step() {
    STEP_NUM=$1
    STEP_DESC=$2
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  PASO $STEP_NUM: $STEP_DESC${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

cmd() {
    echo -e "${GREEN}  \$ $1${NC}"
    if [ "$EXECUTE_MODE" = true ]; then
        eval "$1"
    fi
}

info() {
    echo -e "${YELLOW}  ℹ️  $1${NC}"
}

warn() {
    echo -e "${RED}  ⚠️  $1${NC}"
}

pause_for_user() {
    if [ "$EXECUTE_MODE" = true ]; then
        echo ""
        read -p "  Presiona ENTER para continuar (Ctrl+C para cancelar)... " 
    fi
}

# ============================================================================
# INICIO
# ============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}${BOLD}           GUÍA DE DESPLIEGUE LIMPIO - DistriSearch HA               ${NC}${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$EXECUTE_MODE" = true ]; then
    warn "MODO EJECUCIÓN ACTIVO - Los comandos se ejecutarán automáticamente"
    warn "Esto ELIMINARÁ todos los servicios y datos existentes"
    pause_for_user
else
    info "Modo guía: Los comandos se muestran pero NO se ejecutan"
    info "Usa --execute para ejecutar automáticamente"
fi

# ============================================================================
# FASE 1: LIMPIEZA COMPLETA
# ============================================================================
step 1 "VERIFICAR ESTADO ACTUAL DEL SWARM"
info "Primero verificamos si hay un Swarm activo"
cmd "docker info --format '{{.Swarm.LocalNodeState}}'"

step 2 "LIMPIAR SERVICIOS EXISTENTES"
info "Eliminamos todos los servicios de DistriSearch"
cmd "docker service ls --filter 'name=distrisearch' -q | xargs -r docker service rm || true"
cmd "docker service ls --filter 'name=node' -q | xargs -r docker service rm || true"
cmd "docker service ls --filter 'name=coordinator' -q | xargs -r docker service rm || true"
cmd "docker service ls --filter 'name=master' -q | xargs -r docker service rm || true"

info "Esperamos a que los servicios se eliminen completamente..."
if [ "$EXECUTE_MODE" = true ]; then
    sleep 10
fi

step 3 "LIMPIAR CONTENEDORES LOCALES"
info "Eliminamos contenedores locales que pudieron quedar"
cmd "docker ps -a --filter 'name=distrisearch' -q | xargs -r docker rm -f || true"
cmd "docker ps -a --filter 'name=mongo' -q | xargs -r docker rm -f || true"
cmd "docker ps -a --filter 'name=redis' -q | xargs -r docker rm -f || true"

step 4 "LIMPIAR VOLÚMENES (OPCIONAL - BORRA DATOS)"
warn "Este paso BORRA TODOS LOS DATOS de MongoDB y Redis"
info "Descomenta las líneas si quieres borrar datos"
echo "  # docker volume ls --filter 'name=node' -q | xargs -r docker volume rm"
echo "  # docker volume ls --filter 'name=distrisearch' -q | xargs -r docker volume rm"

step 5 "LIMPIAR RED"
info "Eliminamos la red del cluster"
cmd "docker network rm distrisearch-network 2>/dev/null || true"

# ============================================================================
# FASE 2: RECONSTRUIR IMAGEN
# ============================================================================
step 6 "RECONSTRUIR IMAGEN DEL SLAVE"
info "Navegamos al directorio de Docker y reconstruimos la imagen"
info "Esto incluye los cambios en partition_tolerant.py e internal.py"
cmd "cd $DOCKER_DIR/slave && docker build --no-cache -t distrisearch/slave:latest ."

step 7 "VERIFICAR IMAGEN"
cmd "docker images | grep distrisearch"

# ============================================================================
# FASE 3: CONFIGURAR SWARM
# ============================================================================
step 8 "INICIALIZAR O VERIFICAR SWARM"
info "Si el Swarm ya existe, este comando falla (está bien)"
cmd "docker swarm init --advertise-addr \$(hostname -I | awk '{print \$1}') 2>/dev/null || echo 'Swarm ya iniciado'"

step 9 "OBTENER TOKENS PARA OTRAS MÁQUINAS"
info "Usa estos comandos en las otras máquinas para unirse:"
echo ""
echo -e "  ${GREEN}Para unirse como MANAGER (recomendado para HA):${NC}"
cmd "docker swarm join-token manager"
echo ""
echo -e "  ${GREEN}Para unirse como WORKER:${NC}"
cmd "docker swarm join-token worker"

step 10 "VERIFICAR NODOS DEL SWARM"
cmd "docker node ls"
pause_for_user

# ============================================================================
# FASE 4: CREAR INFRAESTRUCTURA BASE
# ============================================================================
step 11 "CREAR RED OVERLAY"
cmd "docker network create --driver overlay --attachable distrisearch-network 2>/dev/null || echo 'Red ya existe'"

step 12 "DESPLEGAR REDIS COORDINADOR (COMPARTIDO)"
info "Redis coordinador para comunicación entre nodos"
cmd "docker service create --name coordinator-redis --network distrisearch-network --replicas 1 redis:7-alpine"

if [ "$EXECUTE_MODE" = true ]; then
    echo "  Esperando a que Redis esté listo..."
    sleep 10
fi

# ============================================================================
# FASE 5: DESPLEGAR NODOS
# ============================================================================
step 13 "DESPLEGAR NODOS HA"
info "Usamos el script de despliegue para crear los nodos"
info "Opciones disponibles:"
echo ""
echo "  # Desplegar 3 nodos distribuidos automáticamente:"
echo "  ./05-deploy-nodes-ha.sh 3"
echo ""
echo "  # Desplegar 2 nodos en la máquina local + 1 en worker-1:"
echo "  ./05-deploy-nodes-ha.sh --local 2 --add-to-host worker-1 1"
echo ""
echo "  # Reconstruir imagen y desplegar:"
echo "  ./05-deploy-nodes-ha.sh 3 --rebuild"
echo ""

cmd "cd $SCRIPT_DIR && ./05-deploy-nodes-ha.sh --status"

pause_for_user

info "Ejecuta el despliegue según tu configuración:"
cmd "cd $SCRIPT_DIR && ./05-deploy-nodes-ha.sh 3 --rebuild"

# ============================================================================
# FASE 6: VERIFICACIÓN
# ============================================================================
step 14 "VERIFICAR SERVICIOS"
cmd "docker service ls"

step 15 "VERIFICAR LOGS DE UN NODO"
cmd "docker service logs distrisearch-node-1 --tail 50 2>/dev/null || echo 'Servicio aún no disponible'"

step 16 "VERIFICAR SALUD DEL CLUSTER"
info "Espera unos segundos y verifica la salud:"
cmd "sleep 10"
cmd "curl -s http://localhost:8001/api/v1/health | python3 -m json.tool 2>/dev/null || echo 'Aún iniciando...'"

step 17 "DIAGNÓSTICO DE TOLERANCIA A FALLOS"
cmd "cd $SCRIPT_DIR && ./diagnose-swarm-ha.sh"

# ============================================================================
# RESUMEN
# ============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}${BOLD}                        RESUMEN DE PASOS                              ${NC}${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  1. Limpieza de servicios anteriores"
echo "  2. Reconstrucción de imagen con cambios"
echo "  3. Verificación/inicialización de Swarm"
echo "  4. Creación de red e infraestructura"
echo "  5. Despliegue de nodos HA"
echo "  6. Verificación de salud"
echo ""
echo -e "${GREEN}Para un despliegue mínimo de prueba:${NC}"
echo ""
echo "  # En la máquina principal (manager):"
echo "  cd deploy/manual-swarm/scripts"
echo "  ./10-full-cleanup.sh --force"
echo "  cd ../../docker/slave && docker build --no-cache -t distrisearch/slave:latest ."
echo "  cd ../../deploy/manual-swarm/scripts"
echo "  ./05-deploy-nodes-ha.sh 3 --local"
echo ""
echo -e "${GREEN}Para verificar tolerancia a fallos:${NC}"
echo ""
echo "  # Detener el nodo líder y verificar que los otros siguen:"
echo "  docker service scale distrisearch-node-1=0"
echo "  curl http://localhost:8002/api/v1/health"
echo ""
echo -e "${GREEN}Para eliminar documentos huérfanos:${NC}"
echo ""
echo "  python3 scripts/diagnose_documents.py --cleanup-orphans"
echo ""

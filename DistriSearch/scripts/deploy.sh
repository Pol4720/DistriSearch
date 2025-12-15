#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# DistriSearch - Script de Despliegue Dinámico
# Soporta N nodos que crecen/decrecen dinámicamente
# ═══════════════════════════════════════════════════════════════════════════
#
# CARACTERÍSTICAS:
#   - El sistema arranca con 0 slaves y crece dinámicamente
#   - Funciona con cualquier número de nodos (incluso 1)
#   - Tolerancia k solo aplica con k+1 instancias (se ajusta automáticamente)
#   - Soporta partición de red (opera con nodos disponibles)
#
# USO:
#   ./deploy.sh [comando] [opciones]
#
# COMANDOS:
#   build           - Construir todas las imágenes
#   start-infra     - Iniciar MongoDB y Redis
#   start-master    - Iniciar el nodo Master  
#   add-slave       - Agregar un nuevo slave (genera ID automáticamente)
#   remove-slave    - Remover un slave por ID
#   start-lb        - Iniciar el Load Balancer
#   status          - Ver estado de todos los contenedores
#   stop            - Detener todos los contenedores
#   clean           - Limpiar contenedores y volúmenes
#   full-deploy     - Despliegue completo (infra + master + lb, sin slaves)
#
# EJEMPLOS:
#   ./deploy.sh build
#   ./deploy.sh full-deploy            # Arranca el sistema SIN slaves
#   ./deploy.sh add-slave              # Agrega un slave cuando esté listo
#   ./deploy.sh add-slave              # Agrega otro slave
#   ./deploy.sh status                 # Ver estado del cluster
#   ./deploy.sh remove-slave slave-x   # Remover un slave
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NETWORK_NAME="distrisearch-net"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# MongoDB 4.4 es la última versión que NO requiere AVX
# Si tu CPU soporta AVX, puedes usar 7.0
MONGO_VERSION="4.4"
REDIS_VERSION="7-alpine"

# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

generate_id() {
    # Genera un ID único de 8 caracteres
    cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 8 | head -n 1
}

wait_for_healthy() {
    local container=$1
    local max_wait=${2:-60}
    local count=0
    
    echo -n "Esperando que $container esté listo..."
    while [ $count -lt $max_wait ]; do
        if docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null | grep -q "healthy"; then
            echo -e " ${GREEN}OK${NC}"
            return 0
        fi
        if docker ps --filter "name=$container" --filter "status=running" -q | grep -q .; then
            sleep 2
        else
            echo -e " ${RED}FAILED${NC}"
            return 1
        fi
        count=$((count + 2))
        echo -n "."
    done
    echo -e " ${YELLOW}TIMEOUT${NC}"
    return 1
}

get_container_ip() {
    docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1" 2>/dev/null
}

list_slaves() {
    docker ps --filter "name=slave-" --format "{{.Names}}" 2>/dev/null | sort
}

count_slaves() {
    docker ps --filter "name=slave-" -q 2>/dev/null | wc -l
}

# ═══════════════════════════════════════════════════════════════════════════
# NETWORK & VOLUMES
# ═══════════════════════════════════════════════════════════════════════════

setup_network() {
    log_step "Configurando red Docker..."
    docker network inspect $NETWORK_NAME >/dev/null 2>&1 || \
        docker network create --driver bridge $NETWORK_NAME
    log_info "Red $NETWORK_NAME lista"
}

setup_volumes() {
    log_step "Creando volúmenes..."
    docker volume create mongodb-data 2>/dev/null || true
    docker volume create redis-data 2>/dev/null || true
    log_info "Volúmenes creados"
}

# ═══════════════════════════════════════════════════════════════════════════
# BUILD
# ═══════════════════════════════════════════════════════════════════════════

build_images() {
    log_step "Construyendo imágenes Docker..."
    cd "$PROJECT_DIR"
    
    log_info "Construyendo imagen Master..."
    docker build -f docker/master/Dockerfile -t distrisearch/master:latest .
    
    log_info "Construyendo imagen Slave..."
    docker build -f docker/slave/Dockerfile -t distrisearch/slave:latest .
    
    log_info "Construyendo imagen Load Balancer..."
    docker build -f docker/load-balancer/Dockerfile -t distrisearch/load-balancer:latest docker/load-balancer/
    
    log_info "Todas las imágenes construidas"
    docker images | grep distrisearch
}

# ═══════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE (MongoDB + Redis)
# ═══════════════════════════════════════════════════════════════════════════

start_infrastructure() {
    log_step "Iniciando infraestructura..."
    
    setup_network
    setup_volumes
    
    # MongoDB
    if docker ps -a --filter "name=^mongodb$" -q | grep -q .; then
        log_warn "MongoDB ya existe, reiniciando..."
        docker start mongodb 2>/dev/null || true
    else
        log_info "Iniciando MongoDB..."
        docker run -d \
            --name mongodb \
            --network $NETWORK_NAME \
            --hostname mongodb \
            -p 27017:27017 \
            -v mongodb-data:/data/db \
            -v "$PROJECT_DIR/docker/mongodb/init-replica.js:/docker-entrypoint-initdb.d/init-replica.js:ro" \
            -e MONGO_INITDB_DATABASE=distrisearch \
            mongo:$MONGO_VERSION \
            --replSet rs0 --bind_ip_all
    fi
    
    log_info "Esperando que MongoDB inicie..."
    sleep 10
    
    # Inicializar replica set (usa mongo para 4.4, mongosh para 5.0+)
    log_info "Inicializando Replica Set..."
    docker exec mongodb mongo --quiet --eval 'rs.initiate({_id: "rs0", members: [{_id: 0, host: "mongodb:27017"}]})' 2>/dev/null || true
    sleep 5
    
    # Redis
    if docker ps -a --filter "name=^redis$" -q | grep -q .; then
        log_warn "Redis ya existe, reiniciando..."
        docker start redis 2>/dev/null || true
    else
        log_info "Iniciando Redis..."
        docker run -d \
            --name redis \
            --network $NETWORK_NAME \
            --hostname redis \
            -p 6379:6379 \
            -v redis-data:/data \
            redis:$REDIS_VERSION
    fi
    
    sleep 3
    log_info "Infraestructura lista"
}

# ═══════════════════════════════════════════════════════════════════════════
# MASTER NODE
# ═══════════════════════════════════════════════════════════════════════════

start_master() {
    log_step "Iniciando Master Node..."
    
    if docker ps --filter "name=^master$" -q | grep -q .; then
        log_warn "Master ya está corriendo"
        return 0
    fi
    
    # Detener si existe pero no corre
    docker rm -f master 2>/dev/null || true
    
    docker run -d \
        --name master \
        --network $NETWORK_NAME \
        --hostname master \
        -p 8001:8001 \
        -e NODE_ID=master-1 \
        -e NODE_ROLE=master \
        -e MONGODB_URI="mongodb://mongodb:27017/distrisearch?replicaSet=rs0" \
        -e REDIS_URL="redis://redis:6379" \
        -e RAFT_PEERS=master-1 \
        -e LOG_LEVEL=INFO \
        -e API_HOST=0.0.0.0 \
        -e API_PORT=8001 \
        distrisearch/master:latest
    
    log_info "Esperando que Master esté listo..."
    sleep 15
    
    if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
        log_info "Master está listo"
    else
        log_warn "Master puede estar iniciando aún..."
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# SLAVE NODES (DINÁMICO)
# ═══════════════════════════════════════════════════════════════════════════

add_slave() {
    local slave_id=${1:-"slave-$(generate_id)"}
    
    log_step "Agregando nuevo slave: $slave_id"
    
    if docker ps --filter "name=^${slave_id}$" -q | grep -q .; then
        log_error "Slave $slave_id ya existe"
        return 1
    fi
    
    # Crear volumen para este slave
    docker volume create "${slave_id}-data" 2>/dev/null || true
    
    # Encontrar puertos disponibles
    local base_port=8100
    local frontend_port=$base_port
    local api_port=$((base_port + 1000))
    
    # Buscar puertos libres
    while netstat -tuln 2>/dev/null | grep -q ":$frontend_port " || \
          docker ps --format '{{.Ports}}' | grep -q "$frontend_port->"; do
        frontend_port=$((frontend_port + 1))
        api_port=$((api_port + 1))
    done
    
    # Obtener IP del master
    local master_ip=$(get_container_ip master)
    if [ -z "$master_ip" ]; then
        log_error "No se puede obtener IP del master. ¿Está corriendo?"
        return 1
    fi
    
    log_info "Iniciando $slave_id (frontend: $frontend_port, api: $api_port)..."
    
    docker run -d \
        --name "$slave_id" \
        --network $NETWORK_NAME \
        --hostname "$slave_id" \
        -p "${frontend_port}:80" \
        -p "${api_port}:8000" \
        -v "${slave_id}-data:/app/data" \
        -e NODE_ID="$slave_id" \
        -e NODE_ROLE=slave \
        -e MASTER_HOST=master \
        -e MASTER_PORT=8001 \
        -e MONGODB_URI="mongodb://mongodb:27017/distrisearch?replicaSet=rs0" \
        -e REDIS_URL="redis://redis:6379" \
        -e REPLICATION_FACTOR=2 \
        -e LOG_LEVEL=INFO \
        -e API_HOST=0.0.0.0 \
        -e API_PORT=8000 \
        distrisearch/slave:latest
    
    log_info "Slave $slave_id iniciado"
    log_info "  Frontend: http://localhost:$frontend_port"
    log_info "  API:      http://localhost:$api_port"
    
    echo "$slave_id"
}

remove_slave() {
    local slave_id=$1
    
    if [ -z "$slave_id" ]; then
        log_error "Uso: $0 remove-slave <slave-id>"
        log_info "Slaves activos:"
        list_slaves
        return 1
    fi
    
    log_step "Removiendo slave: $slave_id"
    
    # Notificar al master antes de remover (graceful drain)
    local master_ip=$(get_container_ip master)
    if [ -n "$master_ip" ]; then
        curl -sf -X POST "http://${master_ip}:8001/api/v1/cluster/nodes/${slave_id}/drain" 2>/dev/null || true
        sleep 5
    fi
    
    docker stop "$slave_id" 2>/dev/null || true
    docker rm "$slave_id" 2>/dev/null || true
    
    log_info "Slave $slave_id removido"
    log_warn "El volumen ${slave_id}-data no fue eliminado. Usa 'docker volume rm ${slave_id}-data' para eliminarlo."
}

# ═══════════════════════════════════════════════════════════════════════════
# LOAD BALANCER
# ═══════════════════════════════════════════════════════════════════════════

start_loadbalancer() {
    log_step "Iniciando Load Balancer..."
    
    if docker ps --filter "name=^load-balancer$" -q | grep -q .; then
        log_warn "Load Balancer ya está corriendo"
        return 0
    fi
    
    docker rm -f load-balancer 2>/dev/null || true
    
    docker run -d \
        --name load-balancer \
        --network $NETWORK_NAME \
        --hostname load-balancer \
        -p 80:80 \
        -p 443:443 \
        -e MASTER_HOST=master \
        -e MASTER_PORT=8001 \
        -e UPDATE_INTERVAL=15 \
        distrisearch/load-balancer:latest
    
    log_info "Load Balancer iniciado"
    log_info "  HTTP:  http://localhost"
    log_info "  HTTPS: https://localhost"
}

# ═══════════════════════════════════════════════════════════════════════════
# STATUS & MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    DISTRISEARCH STATUS${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    echo -e "${GREEN}Contenedores:${NC}"
    docker ps --filter "network=$NETWORK_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  (ninguno)"
    
    echo ""
    echo -e "${GREEN}Slaves activos:${NC} $(count_slaves)"
    list_slaves | while read slave; do
        local ip=$(get_container_ip "$slave")
        echo "  - $slave ($ip)"
    done
    
    echo ""
    echo -e "${GREEN}Health Checks:${NC}"
    echo -n "  Load Balancer: "
    curl -sf http://localhost/health >/dev/null 2>&1 && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
    
    echo -n "  Master API:    "
    curl -sf http://localhost:8001/api/v1/health/live >/dev/null 2>&1 && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
    
    echo -n "  MongoDB:       "
    docker exec mongodb mongo --quiet --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q "1" && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
    
    echo -n "  Redis:         "
    docker exec redis redis-cli ping 2>/dev/null | grep -q "PONG" && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
    
    echo ""
}

stop_all() {
    log_step "Deteniendo todos los contenedores..."
    
    # Orden: LB -> Slaves -> Master -> Infra
    docker stop load-balancer 2>/dev/null || true
    
    for slave in $(list_slaves); do
        docker stop "$slave" 2>/dev/null || true
    done
    
    docker stop master 2>/dev/null || true
    docker stop redis 2>/dev/null || true
    docker stop mongodb 2>/dev/null || true
    
    log_info "Todos los contenedores detenidos"
}

clean_all() {
    log_step "Limpiando todos los recursos..."
    
    stop_all
    
    # Remover contenedores
    docker rm -f load-balancer master redis mongodb 2>/dev/null || true
    for slave in $(docker ps -a --filter "name=slave-" --format "{{.Names}}"); do
        docker rm -f "$slave" 2>/dev/null || true
    done
    
    read -p "¿Eliminar también los volúmenes de datos? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume rm mongodb-data redis-data 2>/dev/null || true
        for vol in $(docker volume ls --filter "name=slave-" --format "{{.Name}}"); do
            docker volume rm "$vol" 2>/dev/null || true
        done
        log_info "Volúmenes eliminados"
    fi
    
    read -p "¿Eliminar la red Docker? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker network rm $NETWORK_NAME 2>/dev/null || true
        log_info "Red eliminada"
    fi
    
    log_info "Limpieza completada"
}

# ═══════════════════════════════════════════════════════════════════════════
# FULL DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════

full_deploy() {
    log_step "Iniciando despliegue del sistema base..."
    
    build_images
    start_infrastructure
    start_master
    
    # NO agregamos slaves automáticamente
    # El sistema debe poder operar con 0 slaves inicialmente
    # y crecer dinámicamente según se agreguen nodos
    
    start_loadbalancer
    
    # Esperar a que todo esté listo
    sleep 5
    
    show_status
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}       ¡SISTEMA BASE DESPLEGADO!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${YELLOW}NOTA: El sistema arranca SIN slaves.${NC}"
    echo -e "  ${YELLOW}Los nodos se agregan dinámicamente según sea necesario.${NC}"
    echo ""
    echo -e "  El sistema puede operar con:"
    echo -e "    - 0 slaves: Solo Master (modo desarrollo/pruebas)"
    echo -e "    - 1 slave:  Sin replicación"
    echo -e "    - 2 slaves: Replicación factor 1"
    echo -e "    - N slaves: Replicación adaptativa"
    echo ""
    echo -e "  Para agregar un slave:"
    echo -e "    ${BLUE}$0 add-slave${NC}"
    echo ""
    echo -e "  Para ver el estado:"
    echo -e "    ${BLUE}$0 status${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

print_usage() {
    echo ""
    echo "DistriSearch - Despliegue Dinámico"
    echo ""
    echo "El sistema soporta N nodos que crecen/decrecen dinámicamente."
    echo "La tolerancia k solo aplica con k+1 instancias operando."
    echo ""
    echo "Uso: $0 <comando> [opciones]"
    echo ""
    echo "Comandos:"
    echo "  build           Construir todas las imágenes Docker"
    echo "  start-infra     Iniciar MongoDB y Redis"
    echo "  start-master    Iniciar el nodo Master"
    echo "  add-slave       Agregar un nuevo slave (ID auto-generado)"
    echo "  remove-slave    Remover un slave por ID"
    echo "  start-lb        Iniciar el Load Balancer"
    echo "  status          Ver estado del cluster"
    echo "  stop            Detener todos los contenedores"
    echo "  clean           Limpiar contenedores y volúmenes"
    echo "  full-deploy     Despliegue base (sin slaves, crecen dinámicamente)"
    echo ""
    echo "Ejemplos:"
    echo "  $0 full-deploy              # Despliega sistema base (0 slaves)"
    echo "  $0 add-slave                # Agregar el primer slave"
    echo "  $0 add-slave                # Agregar otro slave (crece a 2)"
    echo "  $0 status                   # Ver estado del cluster"
    echo "  $0 remove-slave slave-abc   # Remover un slave (decrece)"
    echo ""
    echo "Comportamiento adaptativo:"
    echo "  - 0 slaves: Sistema base sin procesamiento distribuido"
    echo "  - 1 slave:  Procesa documentos, sin replicación"
    echo "  - 2 slaves: Replicación factor 1"
    echo "  - 3+ slaves: Replicación y tolerancia a fallos"
    echo ""
}

case "${1:-}" in
    build)
        build_images
        ;;
    start-infra)
        start_infrastructure
        ;;
    start-master)
        start_master
        ;;
    add-slave)
        add_slave "$2"
        ;;
    remove-slave)
        remove_slave "$2"
        ;;
    start-lb)
        start_loadbalancer
        ;;
    status)
        show_status
        ;;
    stop)
        stop_all
        ;;
    clean)
        clean_all
        ;;
    full-deploy)
        full_deploy
        ;;
    *)
        print_usage
        exit 1
        ;;
esac

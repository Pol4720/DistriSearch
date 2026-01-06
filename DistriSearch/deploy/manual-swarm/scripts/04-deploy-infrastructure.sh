#!/bin/bash
# ============================================================================
# 04-deploy-infrastructure.sh - Despliega infraestructura del Master
# ============================================================================
# Ejecutar SOLO en el MANAGER
# 
# ARQUITECTURA AP (ACTUAL):
# - SQLite (Raft-replicado): Usuarios, nodos, particiones (metadatos cluster)
# - Redis: Cache de sesiones y coordinación
# - Cada SLAVE tendrá su propio MongoDB + Redis LOCAL (script 06)
#
# NOTA: El MASTER NO necesita MongoDB. Los metadatos del cluster están en
# SQLite. Solo los SLAVES tienen MongoDB para almacenar documentos.
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Infraestructura Master (AP)"
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
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1 (ya existe)"; }

echo ""
echo -e "${CYAN}Arquitectura AP (Almacenamiento):${NC}"
echo "  • SQLite (Raft): Usuarios, nodos, particiones (metadatos cluster)"
echo "  • Redis: Cache de sesiones, coordinación"
echo "  • Gossip Protocol: UserDocumentRegistry (user->docs mapping)"
echo "  • NOTA: El Master NO almacena documentos, solo coordina"
echo ""

# ============================================================================
# 1. Verificar que somos manager
# ============================================================================
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
if [ "$IS_MANAGER" != "true" ]; then
    log_error "Este script debe ejecutarse en un nodo MANAGER"
    exit 1
fi

log_info "Nodo Manager confirmado"

# ============================================================================
# 2. Verificar/Crear red overlay
# ============================================================================
NETWORK_EXISTS=$(docker network ls --filter name=distrisearch-network --filter driver=overlay --format "{{.Name}}" 2>/dev/null)

if [ "$NETWORK_EXISTS" = "distrisearch-network" ]; then
    log_skip "Red distrisearch-network (overlay)"
else
    # Eliminar red si existe pero no es overlay
    docker network rm distrisearch-network 2>/dev/null || true
    
    log_info "Creando red overlay..."
    docker network create \
        --driver overlay \
        --attachable \
        --subnet 10.0.10.0/24 \
        distrisearch-network
    log_info "Red overlay creada"
fi

# ============================================================================
# 3. Desplegar Redis del MASTER (coordinación y cache de sesiones)
# ============================================================================
if docker service inspect master-redis &>/dev/null; then
    log_skip "master-redis"
else
    log_info "Desplegando Redis para el Master (coordinación/cache)..."
    
    # Crear volumen para persistencia
    docker volume create master-redis-data 2>/dev/null || true
    
    docker service create \
        --name master-redis \
        --network distrisearch-network \
        --mount type=volume,source=master-redis-data,target=/data \
        --replicas 1 \
        --constraint 'node.role==manager' \
        --publish 6379:6379 \
        redis:7-alpine redis-server --appendonly yes
    
    log_info "Redis del Master desplegado"
fi

# ============================================================================
# 4. Esperar a que esté listo
# ============================================================================
log_info "Esperando a que Redis esté listo..."

echo -n "Master Redis: "
for i in {1..30}; do
    if docker service ps master-redis --format "{{.CurrentState}}" | grep -q "Running"; then
        echo -e "${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# ============================================================================
# 5. Crear directorio para SQLite (cluster metadata + usuarios)
# ============================================================================
log_info "Preparando directorio para SQLite..."

mkdir -p /opt/distrisearch/data/sqlite
mkdir -p /opt/distrisearch/data/raft
chmod 755 /opt/distrisearch/data/sqlite /opt/distrisearch/data/raft

# ============================================================================
# 6. Verificar estado
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Infraestructura Master Desplegada${NC}"
echo "=============================================="
echo ""
log_info "Estado de los servicios:"
docker service ls | grep -E "master-redis"
echo ""

echo -e "${BLUE}Arquitectura de Datos (AP Mode):${NC}"
echo ""
echo "  MASTER (Coordinador):"
echo "    • SQLite (Raft-replicado)"
echo "      └─ Tablas: users, nodes, partitions (metadatos cluster)"
echo "      └─ Ubicación: /app/data/sqlite/master.db"
echo "    • Redis (master-redis:6379)"
echo "      └─ Cache de sesiones JWT, coordinación"
echo "    • NO tiene MongoDB (no almacena documentos)"
echo ""
echo "  SLAVES (se crean en script 06):"
echo "    • SQLite (réplica Raft)"
echo "      └─ Réplica de users, nodes, partitions"
echo "    • MongoDB local"
echo "      └─ Documentos asignados a ese nodo (VP-Tree)"
echo "    • Redis local"
echo "      └─ Cache de vectores, resultados de búsqueda"
echo ""
echo -e "${CYAN}Protocolos:${NC}"
echo "  • Raft: Consenso para SQLite (users, nodes, partitions)"
echo "  • Gossip: UserDocumentRegistry (user->docs mapping)"
echo "  • VP-Tree: Distribución de documentos entre slaves"
echo ""
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar 05-deploy-master.sh para desplegar el coordinador"

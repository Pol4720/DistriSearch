#!/bin/bash
# ============================================================================
# 04-deploy-infrastructure.sh - Despliega infraestructura del Master
# ============================================================================
# Ejecutar SOLO en el MANAGER
# 
# ARQUITECTURA AP:
# - Master tiene MongoDB para metadatos del cluster (nodos, particiones)
# - Master tiene Redis para cache de sesiones y coordinación
# - Master tiene SQLite embebido para usuarios (replicado via Raft)
# - Cada SLAVE tendrá su propio MongoDB + Redis LOCAL (script 06)
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

echo ""
echo -e "${CYAN}Arquitectura AP:${NC}"
echo "  • Cada nodo (Master + Slaves) tiene su propio MongoDB + Redis"
echo "  • SQLite para usuarios, replicada via Raft entre todos los nodos"
echo "  • Documentos distribuidos con VP-Tree, cada slave almacena local"
echo "  • UserDocumentRegistry via Gossip para saber qué docs tiene cada user"
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
# 2. Verificar red
# ============================================================================
if ! docker network ls | grep -q "distrisearch-network"; then
    log_info "Creando red overlay..."
    docker network create \
        --driver overlay \
        --attachable \
        --subnet 10.0.10.0/24 \
        distrisearch-network
fi

# ============================================================================
# 3. Desplegar MongoDB del MASTER (metadatos del cluster)
# ============================================================================
log_info "Desplegando MongoDB para el Master (metadatos cluster)..."

# Crear volumen para persistencia
docker volume create master-mongo-data 2>/dev/null || true

# Eliminar servicio anterior si existe
docker service rm master-mongo 2>/dev/null || true

docker service create \
    --name master-mongo \
    --network distrisearch-network \
    --mount type=volume,source=master-mongo-data,target=/data/db \
    --replicas 1 \
    --env MONGO_INITDB_DATABASE=distrisearch_master \
    --constraint 'node.role==manager' \
    --publish 27017:27017 \
    mongo:6.0

log_info "MongoDB del Master desplegado"

# ============================================================================
# 4. Desplegar Redis del MASTER (coordinación y cache de sesiones)
# ============================================================================
log_info "Desplegando Redis para el Master (coordinación)..."

# Crear volumen para persistencia
docker volume create master-redis-data 2>/dev/null || true

# Eliminar servicio anterior si existe
docker service rm master-redis 2>/dev/null || true

docker service create \
    --name master-redis \
    --network distrisearch-network \
    --mount type=volume,source=master-redis-data,target=/data \
    --replicas 1 \
    --constraint 'node.role==manager' \
    --publish 6379:6379 \
    redis:7-alpine redis-server --appendonly yes

log_info "Redis del Master desplegado"

# ============================================================================
# 5. Esperar a que estén listos
# ============================================================================
log_info "Esperando a que los servicios estén listos..."

echo -n "Master MongoDB: "
for i in {1..30}; do
    if docker service ps master-mongo --format "{{.CurrentState}}" | grep -q "Running"; then
        echo -e "${GREEN}OK${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

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
# 6. Crear directorio para SQLite (usuarios)
# ============================================================================
log_info "Preparando directorio para SQLite de usuarios..."

mkdir -p /opt/distrisearch/data/users
chmod 755 /opt/distrisearch/data/users

# ============================================================================
# 7. Verificar estado
# ============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  Infraestructura Master Desplegada${NC}"
echo "=============================================="
echo ""
log_info "Estado de los servicios:"
docker service ls | grep -E "master-mongo|master-redis"
echo ""

echo -e "${BLUE}Arquitectura de Datos:${NC}"
echo ""
echo "  MASTER:"
echo "    • MongoDB (master-mongo:27017)"
echo "      └─ Colecciones: nodes, partitions, cluster_state"
echo "    • Redis (master-redis:6379)"
echo "      └─ Cache de sesiones JWT, coordinación Raft"
echo "    • SQLite (/opt/distrisearch/data/users/users.db)"
echo "      └─ Tabla users - replicada via Raft a slaves"
echo ""
echo "  SLAVES (se crean en script 06):"
echo "    • Cada slave tendrá su propio MongoDB local"
echo "      └─ Colecciones: documents (solo los asignados a ese nodo)"
echo "    • Cada slave tendrá su propio Redis local"
echo "      └─ Cache de vectores, resultados de búsqueda"
echo "    • Réplica read-only de SQLite de usuarios"
echo ""
echo -e "${YELLOW}Nota:${NC} Los documentos se distribuyen entre slaves según VP-Tree."
echo "Cada slave solo almacena los documentos de sus particiones asignadas."
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar 05-deploy-master.sh para desplegar el coordinador"

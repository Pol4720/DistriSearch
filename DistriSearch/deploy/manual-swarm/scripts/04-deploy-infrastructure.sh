#!/bin/bash
# ============================================================================
# 04-deploy-infrastructure.sh - Despliega infraestructura del Master
# ============================================================================
# Ejecutar SOLO en el MANAGER
# 
# ARQUITECTURA AP (ACTUAL):
# - SQLite (Raft-replicado): Usuarios, nodos, particiones ← Reemplaza MongoDB
# - MongoDB LOCAL por nodo: Solo para documentos (opcional en Master)
# - Redis: Cache de sesiones y coordinación
# - Cada SLAVE tendrá su propio MongoDB + Redis LOCAL (script 06)
#
# NOTA: Los metadatos del cluster (nodos, particiones) ahora se almacenan
# en SQLite, NO en MongoDB. MongoDB solo se usa para documentos.
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
echo "  • MongoDB LOCAL: Documentos (cada nodo tiene su instancia)"
echo "  • Redis LOCAL: Cache de sesiones, vectores, coordinación"
echo "  • Gossip Protocol: UserDocumentRegistry (user->docs mapping)"
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
if docker network ls | grep -q "distrisearch-network"; then
    log_skip "Red distrisearch-network"
else
    log_info "Creando red overlay..."
    docker network create \
        --driver overlay \
        --attachable \
        --subnet 10.0.10.0/24 \
        distrisearch-network
fi

# ============================================================================
# 3. Desplegar MongoDB del MASTER (documentos locales, OPCIONAL)
# ============================================================================
# NOTA: MongoDB en el Master solo almacena documentos locales (si los hay).
# Los metadatos del cluster (nodos, particiones) están en SQLite.
# ============================================================================
if docker service inspect master-mongo &>/dev/null; then
    log_skip "master-mongo"
else
    log_info "Desplegando MongoDB para el Master (documentos locales)..."
    
    # Crear volumen para persistencia
    docker volume create master-mongo-data 2>/dev/null || true
    
    docker service create \
        --name master-mongo \
        --network distrisearch-network \
        --mount type=volume,source=master-mongo-data,target=/data/db \
        --replicas 1 \
        --env MONGO_INITDB_DATABASE=distrisearch_master \
        --constraint 'node.role==manager' \
        --publish 27017:27017 \
        mongo:7.0 \
        mongod --bind_ip_all
    
    log_info "MongoDB del Master desplegado"
fi

# ============================================================================
# 4. Desplegar Redis del MASTER (coordinación y cache de sesiones)
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
# 6. Crear directorio para SQLite (cluster metadata + usuarios)
# ============================================================================
log_info "Preparando directorio para SQLite..."

mkdir -p /opt/distrisearch/data/sqlite
mkdir -p /opt/distrisearch/data/raft
chmod 755 /opt/distrisearch/data/sqlite /opt/distrisearch/data/raft

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

echo -e "${BLUE}Arquitectura de Datos (AP Mode):${NC}"
echo ""
echo "  MASTER:"
echo "    • SQLite (Raft-replicado)"
echo "      └─ Tablas: users, nodes, partitions (metadatos cluster)"
echo "      └─ Ubicación: /app/data/sqlite/master.db"
echo "    • MongoDB (master-mongo:27017) - OPCIONAL"
echo "      └─ Solo para documentos locales del master"
echo "    • Redis (master-redis:6379)"
echo "      └─ Cache de sesiones JWT, coordinación"
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

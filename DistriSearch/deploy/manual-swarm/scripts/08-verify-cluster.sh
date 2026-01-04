#!/bin/bash
# ============================================================================
# 08-verify-cluster.sh - Verifica el estado completo del cluster
# ============================================================================
# Ejecutar en el MANAGER para verificar que todo funciona
# ============================================================================

set -e

echo "=============================================="
echo "  DistriSearch - Verificación del Cluster"
echo "=============================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS="${GREEN}✓${NC}"
FAIL="${RED}✗${NC}"
WARN="${YELLOW}⚠${NC}"

log_section() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }
log_check() { echo -e "  $1 $2"; }

ERRORS=0
WARNINGS=0

# ============================================================================
# 1. VERIFICAR SWARM
# ============================================================================
log_section "Docker Swarm"

# Verificar que estamos en un swarm
SWARM_STATUS=$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null)
if [ "$SWARM_STATUS" == "active" ]; then
    log_check "$PASS" "Swarm activo"
else
    log_check "$FAIL" "Swarm no activo"
    ((ERRORS++))
fi

# Contar nodos
TOTAL_NODES=$(docker node ls --format "{{.ID}}" 2>/dev/null | wc -l)
READY_NODES=$(docker node ls --filter "node.label!=down" --format "{{.Status}}" 2>/dev/null | grep -c "Ready" || echo "0")
MANAGER_NODES=$(docker node ls --filter "role=manager" --format "{{.ID}}" 2>/dev/null | wc -l)
WORKER_NODES=$(docker node ls --filter "role=worker" --format "{{.ID}}" 2>/dev/null | wc -l)

log_check "$PASS" "Nodos totales: $TOTAL_NODES (Managers: $MANAGER_NODES, Workers: $WORKER_NODES)"

if [ "$READY_NODES" -lt "$TOTAL_NODES" ]; then
    log_check "$WARN" "Algunos nodos no están Ready ($READY_NODES/$TOTAL_NODES)"
    ((WARNINGS++))
else
    log_check "$PASS" "Todos los nodos Ready"
fi

# ============================================================================
# 2. VERIFICAR RED
# ============================================================================
log_section "Red Overlay"

if docker network ls | grep -q "distrisearch-network"; then
    log_check "$PASS" "Red distrisearch-network existe"
    
    # Verificar configuración de la red
    SUBNET=$(docker network inspect distrisearch-network --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null)
    log_check "$PASS" "Subnet: $SUBNET"
else
    log_check "$FAIL" "Red distrisearch-network NO existe"
    ((ERRORS++))
fi

# ============================================================================
# 3. VERIFICAR SERVICIOS
# ============================================================================
log_section "Servicios"

check_service() {
    SERVICE_NAME=$1
    EXPECTED_REPLICAS=$2
    
    if docker service inspect $SERVICE_NAME &>/dev/null; then
        RUNNING=$(docker service ps $SERVICE_NAME --format "{{.CurrentState}}" 2>/dev/null | grep -c "Running" || echo "0")
        DESIRED=$(docker service inspect $SERVICE_NAME --format '{{.Spec.Mode.Replicated.Replicas}}' 2>/dev/null || echo "?")
        
        if [ "$RUNNING" -ge "$EXPECTED_REPLICAS" ]; then
            log_check "$PASS" "$SERVICE_NAME: $RUNNING/$DESIRED réplicas"
        else
            log_check "$WARN" "$SERVICE_NAME: $RUNNING/$DESIRED réplicas (esperado: $EXPECTED_REPLICAS)"
            ((WARNINGS++))
        fi
    else
        log_check "$FAIL" "$SERVICE_NAME: NO DESPLEGADO"
        ((ERRORS++))
    fi
}

check_service "mongo" 1
check_service "redis" 1
check_service "distrisearch-master" 1
check_service "distrisearch-slave" 1
check_service "distrisearch-frontend" 1

# ============================================================================
# 4. VERIFICAR CONECTIVIDAD
# ============================================================================
log_section "Conectividad"

MANAGER_IP=$(docker node inspect self --format '{{.Status.Addr}}' 2>/dev/null)
log_check "$PASS" "IP del Manager: $MANAGER_IP"

# Verificar API del Master
if curl -s -f http://$MANAGER_IP:8000/health &>/dev/null; then
    log_check "$PASS" "API Master respondiendo (puerto 8000)"
else
    log_check "$FAIL" "API Master NO responde"
    ((ERRORS++))
fi

# Verificar Frontend
if curl -s -f http://$MANAGER_IP:3000 &>/dev/null; then
    log_check "$PASS" "Frontend respondiendo (puerto 3000)"
else
    log_check "$WARN" "Frontend no responde (puede no estar desplegado)"
    ((WARNINGS++))
fi

# ============================================================================
# 5. VERIFICAR CLUSTER DISTRISEARCH
# ============================================================================
log_section "Estado del Cluster DistriSearch"

CLUSTER_STATUS=$(curl -s http://$MANAGER_IP:8000/cluster/status 2>/dev/null)

if [ -n "$CLUSTER_STATUS" ] && echo "$CLUSTER_STATUS" | grep -q "node"; then
    log_check "$PASS" "Endpoint /cluster/status responde"
    
    # Extraer información del cluster
    NODE_COUNT=$(echo "$CLUSTER_STATUS" | grep -o '"node_count":[0-9]*' | grep -o '[0-9]*' 2>/dev/null || echo "?")
    LEADER=$(echo "$CLUSTER_STATUS" | grep -o '"leader":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "?")
    
    log_check "$PASS" "Nodos en cluster: $NODE_COUNT"
    log_check "$PASS" "Líder actual: $LEADER"
else
    log_check "$WARN" "No se pudo obtener estado del cluster"
    ((WARNINGS++))
fi

# ============================================================================
# 6. VERIFICAR RAFT (CONSENSO)
# ============================================================================
log_section "Consenso Raft"

RAFT_STATUS=$(curl -s http://$MANAGER_IP:8000/cluster/raft/status 2>/dev/null)

if [ -n "$RAFT_STATUS" ] && echo "$RAFT_STATUS" | grep -q "state"; then
    log_check "$PASS" "Raft activo"
    
    RAFT_STATE=$(echo "$RAFT_STATUS" | grep -o '"state":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "?")
    RAFT_TERM=$(echo "$RAFT_STATUS" | grep -o '"term":[0-9]*' | grep -o '[0-9]*' 2>/dev/null || echo "?")
    
    log_check "$PASS" "Estado: $RAFT_STATE"
    log_check "$PASS" "Term: $RAFT_TERM"
else
    log_check "$WARN" "No se pudo verificar Raft (puede no estar expuesto)"
    ((WARNINGS++))
fi

# ============================================================================
# 7. VERIFICAR PARTICIONAMIENTO VP-TREE
# ============================================================================
log_section "Particionamiento VP-Tree"

PARTITION_STATUS=$(curl -s http://$MANAGER_IP:8000/cluster/partitions 2>/dev/null)

if [ -n "$PARTITION_STATUS" ] && echo "$PARTITION_STATUS" | grep -q "partition"; then
    log_check "$PASS" "VP-Tree configurado"
    
    NUM_PARTITIONS=$(echo "$PARTITION_STATUS" | grep -o '"count":[0-9]*' | grep -o '[0-9]*' 2>/dev/null || echo "?")
    log_check "$PASS" "Particiones: $NUM_PARTITIONS"
else
    log_check "$WARN" "No se pudo verificar particionamiento"
    ((WARNINGS++))
fi

# ============================================================================
# 8. VERIFICAR REPLICACIÓN
# ============================================================================
log_section "Replicación"

REPLICATION_STATUS=$(curl -s http://$MANAGER_IP:8000/cluster/replication 2>/dev/null)

if [ -n "$REPLICATION_STATUS" ]; then
    log_check "$PASS" "Sistema de replicación activo"
    
    REP_FACTOR=$(echo "$REPLICATION_STATUS" | grep -o '"replication_factor":[0-9]*' | grep -o '[0-9]*' 2>/dev/null || echo "?")
    log_check "$PASS" "Factor de replicación: $REP_FACTOR"
else
    log_check "$WARN" "No se pudo verificar replicación"
    ((WARNINGS++))
fi

# ============================================================================
# 9. PRUEBA DE BÚSQUEDA
# ============================================================================
log_section "Prueba de Búsqueda"

SEARCH_RESULT=$(curl -s -X POST http://$MANAGER_IP:8000/search \
    -H "Content-Type: application/json" \
    -d '{"query":"test","search_type":"HYBRID","limit":5}' 2>/dev/null)

if [ -n "$SEARCH_RESULT" ]; then
    if echo "$SEARCH_RESULT" | grep -q "results\|error"; then
        log_check "$PASS" "Endpoint de búsqueda funcional"
    else
        log_check "$WARN" "Respuesta de búsqueda inesperada"
        ((WARNINGS++))
    fi
else
    log_check "$FAIL" "Búsqueda no responde"
    ((ERRORS++))
fi

# ============================================================================
# 10. RESUMEN
# ============================================================================
echo ""
echo "=============================================="
echo "  RESUMEN DE VERIFICACIÓN"
echo "=============================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}  ✓ CLUSTER COMPLETAMENTE OPERATIVO${NC}"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}  ⚠ CLUSTER OPERATIVO CON ADVERTENCIAS${NC}"
else
    echo -e "${RED}  ✗ CLUSTER CON ERRORES${NC}"
fi

echo ""
echo "  Errores:      $ERRORS"
echo "  Advertencias: $WARNINGS"
echo ""

# Mostrar URLs de acceso
echo -e "${BLUE}URLs de Acceso:${NC}"
echo "  Frontend:     http://$MANAGER_IP:3000"
echo "  API:          http://$MANAGER_IP:8000"
echo "  API Docs:     http://$MANAGER_IP:8000/docs"
echo ""

# Comandos útiles
echo -e "${BLUE}Comandos Útiles:${NC}"
echo "  docker service ls                          # Ver servicios"
echo "  docker service logs -f distrisearch-master # Ver logs del master"
echo "  docker node ls                             # Ver nodos"
echo "  docker service ps distrisearch-slave       # Ver distribución de slaves"
echo ""

exit $ERRORS

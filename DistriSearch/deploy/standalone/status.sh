#!/bin/bash
# ============================================================================
# status.sh - Ver estado de todos los componentes DistriSearch
# ============================================================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          ESTADO DEL CLUSTER DISTRISEARCH                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar Swarm
echo -e "${GREEN}Estado de Docker Swarm:${NC}"
if docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    SWARM_ROLE=$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)
    if [ "$SWARM_ROLE" = "true" ]; then
        echo -e "  Estado: ${GREEN}Activo (Manager)${NC}"
    else
        echo -e "  Estado: ${GREEN}Activo (Worker)${NC}"
    fi
    docker node ls 2>/dev/null | head -5 || true
else
    echo -e "  Estado: ${RED}No activo${NC}"
fi
echo ""

# Verificar red overlay
echo -e "${GREEN}Red Overlay:${NC}"
if docker network ls --format '{{.Name}}' | grep -q "^distrisearch-network$"; then
    echo -e "  distrisearch-network: ${GREEN}✅ Existe${NC}"
else
    echo -e "  distrisearch-network: ${RED}❌ No existe${NC}"
fi
echo ""

# Mostrar todos los contenedores DistriSearch
echo -e "${GREEN}Contenedores DistriSearch:${NC}"
docker ps -a --filter "name=distrisearch-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10

echo ""

# IPs
MACHINE_A_IP="192.168.61.32"
MACHINE_B_IP="192.168.61.33"

# Estado de servicios de infraestructura
echo -e "${GREEN}Servicios de Infraestructura:${NC}"

# CoreDNS
echo -n "  CoreDNS (127.0.0.1:5353): "
if command -v dig &> /dev/null; then
    if dig @127.0.0.1 -p 5353 distrisearch.local +short +time=1 &>/dev/null; then
        echo -e "${GREEN}✅ ONLINE${NC}"
    else
        echo -e "${RED}❌ OFFLINE${NC}"
    fi
else
    if docker ps --format '{{.Names}}' | grep -q "distrisearch-coredns"; then
        echo -e "${GREEN}✅ RUNNING${NC}"
    else
        echo -e "${RED}❌ STOPPED${NC}"
    fi
fi

# Load Balancer
echo -n "  Load Balancer (localhost:80): "
if curl -sf --max-time 2 "http://localhost/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ONLINE${NC}"
else
    if docker ps --format '{{.Names}}' | grep -q "distrisearch-loadbalancer"; then
        echo -e "${YELLOW}⚠️  RUNNING (sin respuesta)${NC}"
    else
        echo -e "${RED}❌ STOPPED${NC}"
    fi
fi

echo ""

# Estado de salud de los nodos
echo -e "${GREEN}Nodos de Aplicación:${NC}"

# Nodo 1
echo -n "  Node-1 (${MACHINE_A_IP}:8001): "
if curl -sf --max-time 2 "http://${MACHINE_A_IP}:8001/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ONLINE${NC}"
else
    echo -e "${RED}❌ OFFLINE${NC}"
fi

# Nodo 2
echo -n "  Node-2 (${MACHINE_A_IP}:8002): "
if curl -sf --max-time 2 "http://${MACHINE_A_IP}:8002/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ONLINE${NC}"
else
    echo -e "${RED}❌ OFFLINE${NC}"
fi

# Nodo 3
echo -n "  Node-3 (${MACHINE_B_IP}:8003): "
if curl -sf --max-time 2 "http://${MACHINE_B_IP}:8003/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ONLINE${NC}"
else
    echo -e "${RED}❌ OFFLINE${NC}"
fi

echo ""

# Mostrar líder actual
echo -e "${GREEN}Información del Cluster (BULLY):${NC}"
for port in 8001 8002 8003; do
    ip="${MACHINE_A_IP}"
    [ $port -eq 8003 ] && ip="${MACHINE_B_IP}"
    
    CLUSTER_INFO=$(curl -sf --max-time 2 "http://${ip}:${port}/api/v1/cluster/status" 2>/dev/null)
    if [ -n "$CLUSTER_INFO" ]; then
        echo "  (Información desde nodo en puerto ${port})"
        echo "$CLUSTER_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Leader: {d.get(\"leader\",\"unknown\")}')" 2>/dev/null || true
        echo "$CLUSTER_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    Nodos conocidos: {len(d.get(\"nodes\",[]))}')" 2>/dev/null || true
        break
    fi
done

echo ""
echo -e "${BLUE}URLs de Acceso:${NC}"
echo "  Load Balancer A: https://${MACHINE_A_IP}:443"
echo "  Load Balancer B: https://${MACHINE_B_IP}:443"
echo ""

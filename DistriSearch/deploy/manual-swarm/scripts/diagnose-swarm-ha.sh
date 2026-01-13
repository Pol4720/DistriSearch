#!/bin/bash
# ============================================================================
# diagnose-swarm-ha.sh - Diagnóstico de tolerancia a fallos del Swarm
# ============================================================================
# Este script verifica:
# 1. Cuántos managers hay y su estado
# 2. Si el quórum es suficiente para tolerancia a fallos
# 3. Servicios con constraints problemáticos
# 4. Recomendaciones para mejorar HA
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "============================================================================"
echo -e "${BLUE}   DIAGNÓSTICO DE TOLERANCIA A FALLOS - DOCKER SWARM${NC}"
echo "============================================================================"
echo ""

# Verificar que estamos en un swarm
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    echo -e "${RED}ERROR: Este nodo no está en un Swarm activo${NC}"
    exit 1
fi

# 1. Información del nodo actual
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  1. NODO ACTUAL${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
CURRENT_NODE=$(docker info --format '{{.Name}}')
IS_MANAGER=$(docker info --format '{{.Swarm.ControlAvailable}}')
echo "   Hostname: $CURRENT_NODE"
echo "   Es Manager: $IS_MANAGER"
echo ""

# 2. Estado de los managers
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  2. ESTADO DE MANAGERS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
docker node ls --format "table {{.ID}}\t{{.Hostname}}\t{{.Status}}\t{{.Availability}}\t{{.ManagerStatus}}"
echo ""

# Contar managers
TOTAL_MANAGERS=$(docker node ls --filter "role=manager" -q | wc -l)
READY_MANAGERS=$(docker node ls --filter "role=manager" --filter "node.label=availability=active" --format "{{.Status}}" 2>/dev/null | grep -c "Ready" || docker node ls --filter "role=manager" --format "{{.Status}}" | grep -c "Ready")
LEADER=$(docker node ls --format "{{.Hostname}}\t{{.ManagerStatus}}" | grep "Leader" | cut -f1 || echo "Ninguno")

echo "   Total managers: $TOTAL_MANAGERS"
echo "   Managers Ready: $READY_MANAGERS"
echo "   Líder actual: $LEADER"
echo ""

# Calcular tolerancia
QUORUM=$(( (TOTAL_MANAGERS / 2) + 1 ))
FAULT_TOLERANCE=$(( TOTAL_MANAGERS - QUORUM ))

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  3. ANÁLISIS DE QUÓRUM${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "   Quórum necesario: $QUORUM de $TOTAL_MANAGERS managers"
echo "   Tolerancia a fallos: $FAULT_TOLERANCE manager(s) pueden fallar"
echo ""

if [ $FAULT_TOLERANCE -eq 0 ]; then
    echo -e "   ${RED}⚠️  ADVERTENCIA: SIN TOLERANCIA A FALLOS${NC}"
    echo -e "   ${RED}   Si cualquier manager se cae, el cluster se vuelve inoperable${NC}"
    echo ""
    if [ $TOTAL_MANAGERS -eq 2 ]; then
        echo -e "   ${YELLOW}RECOMENDACIÓN: Añadir 1 manager más para tener tolerancia a 1 fallo${NC}"
        echo "   Ejecutar en un nuevo nodo:"
        echo "      docker swarm join --token \$(docker swarm join-token manager -q) <IP_MANAGER>:2377"
    fi
elif [ $FAULT_TOLERANCE -eq 1 ]; then
    echo -e "   ${YELLOW}⚡ TOLERANCIA BÁSICA: 1 manager puede fallar${NC}"
    echo "   El cluster seguirá funcionando si pierde hasta 1 manager"
elif [ $FAULT_TOLERANCE -ge 2 ]; then
    echo -e "   ${GREEN}✅ BUENA TOLERANCIA: $FAULT_TOLERANCE managers pueden fallar${NC}"
fi
echo ""

# 4. Servicios con constraints de hostname
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  4. SERVICIOS CON RESTRICCIONES DE HOSTNAME${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

CONSTRAINED_SERVICES=0
while IFS= read -r service; do
    CONSTRAINTS=$(docker service inspect "$service" --format '{{range .Spec.TaskTemplate.Placement.Constraints}}{{.}}{{"\n"}}{{end}}' 2>/dev/null || true)
    if echo "$CONSTRAINTS" | grep -q "node.hostname"; then
        HOSTNAME_CONSTRAINT=$(echo "$CONSTRAINTS" | grep "node.hostname" | head -1)
        echo -e "   ${YELLOW}⚠️  $service${NC}"
        echo "      Constraint: $HOSTNAME_CONSTRAINT"
        CONSTRAINED_SERVICES=$((CONSTRAINED_SERVICES + 1))
    fi
done < <(docker service ls --format "{{.Name}}")

if [ $CONSTRAINED_SERVICES -eq 0 ]; then
    echo -e "   ${GREEN}✅ Ningún servicio tiene restricción de hostname${NC}"
else
    echo ""
    echo -e "   ${YELLOW}Total: $CONSTRAINED_SERVICES servicios fijados a hosts específicos${NC}"
    echo ""
    echo "   NOTA: Estos servicios NO se moverán si su host falla."
    echo "   Esto es INTENCIONAL para DistriSearch (cada nodo tiene su MongoDB local)."
    echo "   La tolerancia a fallos se maneja a nivel de APLICACIÓN, no de Swarm."
fi
echo ""

# 5. Verificar servicios actuales
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  5. ESTADO DE SERVICIOS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
docker service ls --format "table {{.Name}}\t{{.Mode}}\t{{.Replicas}}\t{{.Image}}"
echo ""

# 6. Servicios con problemas
PROBLEM_SERVICES=$(docker service ls --format "{{.Name}}\t{{.Replicas}}" | grep -v "1/1\|0/0" | grep -v "Replicas" || true)
if [ -n "$PROBLEM_SERVICES" ]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  6. SERVICIOS CON PROBLEMAS${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${RED}$PROBLEM_SERVICES${NC}"
    echo ""
fi

# 7. Recomendaciones
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  7. RESUMEN Y RECOMENDACIONES${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Arquitectura actual de DistriSearch
echo "   ARQUITECTURA ACTUAL DE DISTRISEARCH:"
echo "   ─────────────────────────────────────"
echo "   • Cada nodo tiene MongoDB + Redis + App LOCALES"
echo "   • Los servicios están FIJADOS a sus hosts (constraints)"
echo "   • Si un host se cae, SUS servicios se caen (es intencional)"
echo "   • La tolerancia a fallos es a nivel de APLICACIÓN:"
echo "     - Algoritmo BULLY elige nuevo líder entre nodos restantes"
echo "     - Los documentos están replicados entre nodos"
echo "     - El sistema sigue funcionando con N-1 nodos"
echo ""

if [ $TOTAL_MANAGERS -lt 3 ]; then
    echo -e "   ${RED}⚠️  PROBLEMA: Solo tienes $TOTAL_MANAGERS managers${NC}"
    echo "   Si el líder Swarm se cae, el cluster Swarm pierde quórum."
    echo "   Aunque la APP tiene tolerancia, Swarm no puede gestionar servicios."
    echo ""
    echo "   SOLUCIÓN: Añadir managers hasta tener mínimo 3"
    echo ""
elif [ $READY_MANAGERS -lt $QUORUM ]; then
    echo -e "   ${RED}⚠️  PROBLEMA: Solo $READY_MANAGERS managers disponibles (necesitas $QUORUM)${NC}"
    echo "   El cluster Swarm no tiene quórum actualmente."
    echo ""
    echo "   SOLUCIÓN: Reconectar o reparar managers caídos"
    echo ""
else
    echo -e "   ${GREEN}✅ El cluster tiene quórum ($READY_MANAGERS/$TOTAL_MANAGERS managers Ready)${NC}"
    echo ""
    echo "   COMPORTAMIENTO ESPERADO cuando cae el líder Swarm:"
    echo "   1. Los otros managers eligen nuevo líder (10-30 segundos)"
    echo "   2. Los servicios en el nodo caído se quedan caídos (constraints)"
    echo "   3. Los servicios en otros nodos SIGUEN funcionando"
    echo "   4. El algoritmo BULLY de DistriSearch elige nuevo líder de app"
    echo ""
fi

echo "============================================================================"
echo ""

#!/bin/bash

echo "========================================"
echo "DistriSearch - Suite de Tests de Robustez"
echo "========================================"

# ✅ NUEVO: Configurar entorno automáticamente
./configure_tests.sh

if [ $? -ne 0 ]; then
    echo "❌ Error en configuración - Abortando"
    exit 1
fi

# Cargar configuración
set -a
source .env.test
set +a

echo ""
echo "🚀 Iniciando tests con:"
echo "   Backend: $BACKEND_URL"
echo "   MongoDB: $MONGO_URI"

# Ejecutar tests críticos primero
echo ""
echo "========== FASE 1: Tests Críticos =========="
pytest test_fault_tolerance.py::TestNodeFailureTolerance -m critical -v -s

if [ $? -ne 0 ]; then
    echo "❌ Tests críticos FALLARON - Abortando"
    exit 1
fi

# Tests de consistencia
echo ""
echo "========== FASE 2: Tests de Consistencia =========="
pytest test_replication_consistency.py -m consistency -v -s

# Tests de disponibilidad
echo ""
echo "========== FASE 3: Tests de Disponibilidad =========="
pytest test_search_availability.py -m availability -v -s

# Stress tests (opcional)
read -p "¿Ejecutar stress tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "========== FASE 4: Stress Tests =========="
    pytest test_fault_tolerance.py::TestContinuousFailureStress -v -s
fi

echo ""
echo "========================================"
echo "✅ Suite de tests completada"
echo "========================================"
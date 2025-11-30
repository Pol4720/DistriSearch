#!/bin/bash

echo "========================================"
echo "DistriSearch - Suite de Tests de Robustez"
echo "========================================"

# Verificar que el backend está corriendo
echo "🔍 Verificando backend..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Error: Backend no está corriendo en http://localhost:8000"
    echo "   Ejecuta primero: cd deploy && docker-compose up -d backend mongo"
    exit 1
fi

echo "✅ Backend detectado"

# Configurar variables de entorno para tests
export BACKEND_URL="http://localhost:8000"
export ADMIN_API_KEY="${ADMIN_API_KEY:-test_key}"
export MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
export MONGO_DBNAME="${MONGO_DBNAME:-distrisearch}"

# Ejecutar tests críticos primero
echo ""
echo "========== FASE 1: Tests Críticos =========="
pytest test/test_fault_tolerance.py::TestNodeFailureTolerance -m critical -v

if [ $? -ne 0 ]; then
    echo "❌ Tests críticos FALLARON - Abortando"
    exit 1
fi

# Tests de consistencia
echo ""
echo "========== FASE 2: Tests de Consistencia =========="
pytest test/test_replication_consistency.py -m consistency -v

# Tests de disponibilidad
echo ""
echo "========== FASE 3: Tests de Disponibilidad =========="
pytest test/test_search_availability.py -m availability -v

# Stress tests (opcional - requiere más tiempo)
read -p "¿Ejecutar stress tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "========== FASE 4: Stress Tests =========="
    pytest test/test_fault_tolerance.py::TestContinuousFailureStress -v
fi

echo ""
echo "========================================"
echo "✅ Suite de tests completada"
echo "========================================"
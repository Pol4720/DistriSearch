"""
Configuración compartida de fixtures para pytest
"""
import os
import sys

# Agregar raíz del proyecto al path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# También agregar subdirectorios necesarios para resolver imports
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def pytest_configure(config):
    """Registrar markers personalizados"""
    config.addinivalue_line("markers", "e2e: tests end-to-end que requieren Docker")
    config.addinivalue_line("markers", "slow: tests que tardan más de 30 segundos")
    config.addinivalue_line("markers", "integration: tests de integración entre módulos")

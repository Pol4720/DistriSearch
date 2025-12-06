"""
DistriSearch Slave - API Routes
================================
Re-exporta rutas desde backend/routes para compatibilidad.
"""

import sys
import os

# Asegurar que backend esté en el path
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Re-exportar todos los routers
from backend.routes import auth, search, register, download, cluster, health

__all__ = [
    "auth",
    "search", 
    "register",
    "download",
    "cluster",
    "health"
]

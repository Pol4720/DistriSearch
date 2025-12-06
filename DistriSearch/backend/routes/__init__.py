"""
DistriSearch Backend - API Routes
=================================
Rutas de la API FastAPI.
"""

from backend.routes import auth
from backend.routes import search
from backend.routes import register
from backend.routes import download
from backend.routes import cluster
from backend.routes import health
from backend.routes import naming
from backend.routes import fault_tolerance

__all__ = [
    "auth",
    "search",
    "register", 
    "download",
    "cluster",
    "health",
    "naming",
    "fault_tolerance"
]

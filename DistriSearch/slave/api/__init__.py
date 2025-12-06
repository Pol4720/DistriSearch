"""
Slave API Module
================
Capa de API REST basada en FastAPI.
"""

from slave.api.main import app, create_app, lifespan

__all__ = ["app", "create_app", "lifespan"]

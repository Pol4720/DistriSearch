"""
DistriSearch Slave Module
=========================
Módulo del nodo Slave que gestiona:
- API REST (FastAPI)
- Escaneo de archivos locales
- Servicios de indexación y replicación

En la arquitectura Master-Slave:
- Slave: Almacena archivos, responde queries, envía heartbeats
- Master: Coordina, indexa ubicaciones, balancea carga
"""

from slave.api import create_app

__all__ = ["create_app"]

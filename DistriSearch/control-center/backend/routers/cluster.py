"""
Cluster Router - Endpoints para estado del cluster
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
router = APIRouter()


def get_cluster_service():
    """Dependency injection for cluster service."""
    from main import get_cluster_service as get_svc
    return get_svc()


@router.get("/status", summary="Estado del cluster")
async def get_cluster_status():
    """
    Obtiene el estado completo del cluster DistriSearch.
    
    Retorna:
    - Estado general (healthy/degraded/unhealthy)
    - Lista de nodos con su estado
    - Estadísticas de documentos y particiones
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    status = await service.get_cluster_status()
    if not status:
        raise HTTPException(status_code=503, detail="No se pudo obtener estado del cluster")
    
    return status


@router.get("/leader", summary="Información del líder")
async def get_leader_info():
    """
    Obtiene información sobre el líder actual del cluster.
    
    Incluye:
    - ID del líder
    - Dirección del líder
    - Término actual de Raft
    - Estado de la elección
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    leader_info = await service.get_leader_info()
    return {
        "leader": leader_info,
        "timestamp": datetime.utcnow().isoformat(),
        "description": {
            "es": "El líder coordina todas las operaciones de escritura y mantiene la consistencia del cluster."
        }
    }


@router.get("/replication", summary="Estado de replicación")
async def get_replication_status():
    """
    Obtiene el estado de replicación de datos en el cluster.
    
    Incluye:
    - Factor de replicación configurado
    - Distribución de documentos por nodo
    - Estado de sincronización
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    replication = await service.get_replication_status()
    return {
        "replication": replication,
        "timestamp": datetime.utcnow().isoformat(),
        "description": {
            "es": "La replicación garantiza que los datos estén disponibles en múltiples nodos para tolerancia a fallos."
        }
    }


@router.get("/health", summary="Health check del cluster")
async def get_cluster_health():
    """
    Realiza un health check completo del cluster.
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    health = await service.get_health()
    return {
        "health": health,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/search", summary="Ejecutar búsqueda")
async def execute_search(query: str):
    """
    Ejecuta una búsqueda en el sistema distribuido.
    
    Permite probar el funcionamiento de la búsqueda distribuida
    y ver cómo se coordinan los nodos para responder.
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    start_time = datetime.utcnow()
    results = await service.execute_search(query)
    end_time = datetime.utcnow()
    
    return {
        "query": query,
        "results": results,
        "execution_time_ms": (end_time - start_time).total_seconds() * 1000,
        "timestamp": end_time.isoformat()
    }

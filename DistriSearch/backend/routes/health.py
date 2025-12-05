"""
DistriSearch Routes - Health Check Endpoints

Endpoints para verificar el estado del servicio y del cluster.
"""
from fastapi import APIRouter, Depends
from typing import Dict, List, Optional
from datetime import datetime
import os
import psutil
import logging

from services import node_service
from services.reliability_metrics import get_reliability_metrics
import database

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["health"],
    responses={404: {"description": "Not found"}},
)


@router.get("")
@router.get("/")
async def health_check() -> Dict:
    """
    Health check básico.
    Retorna OK si el servicio está funcionando.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "DistriSearch",
        "node_id": os.getenv("NODE_ID", "unknown")
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict:
    """
    Health check detallado con métricas del sistema.
    """
    node_id = os.getenv("NODE_ID", "unknown")
    node_role = os.getenv("NODE_ROLE", "slave")
    
    # Métricas del sistema
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Estado de MongoDB
    mongo_healthy = False
    mongo_latency_ms = None
    try:
        start = datetime.utcnow()
        database._client.admin.command('ping')
        mongo_latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
        mongo_healthy = True
    except Exception as e:
        logger.warning(f"MongoDB health check failed: {e}")
    
    # Contar documentos y nodos
    total_files = 0
    total_nodes = 0
    try:
        total_files = database._db.files.count_documents({})
        total_nodes = database._db.nodes.count_documents({})
    except Exception:
        pass
    
    return {
        "status": "healthy" if mongo_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "node": {
            "id": node_id,
            "role": node_role,
            "uptime_seconds": get_uptime_seconds()
        },
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2)
        },
        "database": {
            "healthy": mongo_healthy,
            "latency_ms": round(mongo_latency_ms, 2) if mongo_latency_ms else None,
            "total_files": total_files,
            "total_nodes": total_nodes
        },
        "version": "1.0.0"
    }


@router.get("/cluster")
async def cluster_health() -> Dict:
    """
    Estado de salud del cluster completo.
    """
    node_id = os.getenv("NODE_ID", "unknown")
    node_role = os.getenv("NODE_ROLE", "slave")
    
    # Obtener todos los nodos
    all_nodes = database.get_all_nodes()
    
    online_nodes = [n for n in all_nodes if n.get('status') == 'online']
    offline_nodes = [n for n in all_nodes if n.get('status') == 'offline']
    
    # Encontrar el master actual (si hay)
    master_node = None
    for node in all_nodes:
        if node.get('is_master') or node.get('node_role') == 'master':
            master_node = node
            break
    
    # Métricas de confiabilidad
    reliability = get_reliability_metrics()
    mttr = reliability.get_mttr()
    mtbf = reliability.get_mtbf()
    
    return {
        "status": "healthy" if len(online_nodes) > 0 else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "this_node": {
            "id": node_id,
            "role": node_role
        },
        "cluster": {
            "total_nodes": len(all_nodes),
            "online_nodes": len(online_nodes),
            "offline_nodes": len(offline_nodes),
            "master": {
                "id": master_node.get('node_id') if master_node else None,
                "ip": master_node.get('ip_address') if master_node else None
            } if master_node else None
        },
        "nodes": [
            {
                "id": n.get('node_id'),
                "status": n.get('status'),
                "last_seen": n.get('last_seen').isoformat() if n.get('last_seen') else None,
                "files_count": n.get('shared_files_count', 0)
            }
            for n in all_nodes
        ],
        "reliability": {
            "mttr_seconds": round(mttr, 2) if mttr else None,
            "mtbf_seconds": round(mtbf, 2) if mtbf else None
        }
    }


@router.get("/ready")
async def readiness_check() -> Dict:
    """
    Readiness probe para Kubernetes/Docker.
    Verifica si el servicio está listo para recibir tráfico.
    """
    ready = True
    checks = {}
    
    # Check MongoDB
    try:
        database._client.admin.command('ping')
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {str(e)}"
        ready = False
    
    # Check que el nodo esté registrado
    node_id = os.getenv("NODE_ID", "unknown")
    try:
        node = database.get_node(node_id)
        if node:
            checks["node_registered"] = "ok"
        else:
            checks["node_registered"] = "not_registered"
            # No marcar como not ready si no está registrado aún
    except Exception as e:
        checks["node_registered"] = f"error: {str(e)}"
    
    return {
        "ready": ready,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@router.get("/live")
async def liveness_check() -> Dict:
    """
    Liveness probe para Kubernetes/Docker.
    Verifica si el servicio está vivo (no colgado).
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    }


# Variable global para tracking de uptime
_start_time = datetime.utcnow()


def get_uptime_seconds() -> float:
    """Retorna segundos desde el inicio del servicio"""
    return (datetime.utcnow() - _start_time).total_seconds()

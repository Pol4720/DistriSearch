"""
Metrics Router - Endpoints para métricas del sistema
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Almacén de métricas históricas
metrics_history: List[Dict[str, Any]] = []
MAX_HISTORY = 100


def get_cluster_service():
    from main import get_cluster_service as get_svc
    return get_svc()


def get_docker_service():
    from main import get_docker_service as get_svc
    return get_svc()


@router.get("/current", summary="Métricas actuales")
async def get_current_metrics():
    """
    Obtiene las métricas actuales del sistema.
    
    Incluye:
    - Estado del cluster
    - Métricas por nodo
    - Estadísticas de documentos
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    metrics = await service.get_metrics()
    
    # Guardar en historial
    metrics_history.append(metrics)
    if len(metrics_history) > MAX_HISTORY:
        metrics_history.pop(0)
    
    return metrics


@router.get("/history", summary="Historial de métricas")
async def get_metrics_history(limit: int = 50):
    """
    Obtiene el historial de métricas.
    
    Útil para visualizar tendencias y cambios en el tiempo.
    """
    return {
        "history": metrics_history[-limit:],
        "total_records": len(metrics_history),
        "returned": min(limit, len(metrics_history))
    }


@router.get("/summary", summary="Resumen de métricas")
async def get_metrics_summary():
    """
    Obtiene un resumen de las métricas del sistema.
    
    Proporciona una vista general del estado del cluster
    con información explicativa en español.
    """
    service = get_cluster_service()
    if not service:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    
    metrics = await service.get_metrics()
    cluster = metrics.get("cluster", {})
    nodes = metrics.get("nodes", [])
    system = metrics.get("system", {})
    
    # Calcular estadísticas
    avg_cpu = sum(n.get("cpu_usage", 0) for n in nodes) / len(nodes) if nodes else 0
    avg_memory = sum(n.get("memory_usage", 0) for n in nodes) / len(nodes) if nodes else 0
    
    # Determinar estado del cluster con explicación
    status = cluster.get("status", "unknown")
    status_info = {
        "healthy": {
            "color": "green",
            "icon": "✅",
            "description_es": "El cluster está funcionando correctamente. Todos los nodos responden y los datos están sincronizados."
        },
        "degraded": {
            "color": "yellow",
            "icon": "⚠️",
            "description_es": "El cluster está en modo degradado. Algunos nodos pueden no estar disponibles, pero el sistema sigue operativo."
        },
        "unhealthy": {
            "color": "red",
            "icon": "❌",
            "description_es": "El cluster no está saludable. Puede haber problemas de conectividad o nodos caídos que requieren atención."
        },
        "unknown": {
            "color": "gray",
            "icon": "❓",
            "description_es": "No se puede determinar el estado del cluster. Verifique la conectividad con el sistema."
        }
    }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cluster_status": {
            "status": status,
            **status_info.get(status, status_info["unknown"])
        },
        "nodes": {
            "total": cluster.get("total_nodes", 0),
            "healthy": cluster.get("healthy_nodes", 0),
            "unhealthy": cluster.get("unhealthy_nodes", 0),
            "description_es": f"El cluster tiene {cluster.get('total_nodes', 0)} nodos, de los cuales {cluster.get('healthy_nodes', 0)} están saludables."
        },
        "data": {
            "total_documents": cluster.get("total_documents", 0),
            "total_partitions": cluster.get("total_partitions", 0),
            "replication_factor": cluster.get("replication_factor", 2),
            "description_es": f"Hay {cluster.get('total_documents', 0)} documentos distribuidos en {cluster.get('total_partitions', 0)} particiones con factor de replicación {cluster.get('replication_factor', 2)}."
        },
        "resources": {
            "avg_cpu_usage": round(avg_cpu, 2),
            "avg_memory_usage": round(avg_memory, 2),
            "description_es": f"Uso promedio de CPU: {round(avg_cpu, 2)}%, Memoria: {round(avg_memory, 2)}%"
        },
        "uptime": {
            "seconds": system.get("uptime_seconds", 0),
            "formatted": format_uptime(system.get("uptime_seconds", 0)),
            "description_es": f"El sistema lleva {format_uptime(system.get('uptime_seconds', 0))} en funcionamiento."
        },
        "concepts": {
            "es": {
                "cluster": "Un cluster es un conjunto de nodos que trabajan juntos para proporcionar alta disponibilidad y escalabilidad.",
                "nodo": "Cada nodo es una instancia del servicio que puede procesar peticiones y almacenar datos.",
                "replicacion": f"Con factor de replicación {cluster.get('replication_factor', 2)}, cada documento se almacena en {cluster.get('replication_factor', 2)} nodos diferentes.",
                "particiones": "Los datos se dividen en particiones para distribuir la carga entre los nodos."
            }
        }
    }


@router.get("/containers", summary="Métricas de contenedores")
async def get_container_metrics():
    """
    Obtiene métricas de los contenedores Docker.
    """
    docker_service = get_docker_service()
    if not docker_service or not docker_service.available:
        return {
            "available": False,
            "message": "Docker no está disponible",
            "containers": []
        }
    
    containers = docker_service.get_distrisearch_containers()
    container_metrics = []
    
    for container in containers:
        if container["status"] == "running":
            stats = docker_service.get_container_stats(container["name"])
            if stats:
                container_metrics.append(stats)
            else:
                container_metrics.append({
                    "container_id": container["id"],
                    "container_name": container["name"],
                    "status": container["status"],
                    "stats_available": False
                })
        else:
            container_metrics.append({
                "container_id": container["id"],
                "container_name": container["name"],
                "status": container["status"],
                "stats_available": False
            })
    
    return {
        "available": True,
        "containers": container_metrics,
        "total": len(container_metrics),
        "timestamp": datetime.utcnow().isoformat()
    }


def format_uptime(seconds: float) -> str:
    """Formatea el uptime en un string legible."""
    if seconds < 60:
        return f"{int(seconds)} segundos"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minutos"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours} horas {minutes} minutos"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        return f"{days} días {hours} horas"

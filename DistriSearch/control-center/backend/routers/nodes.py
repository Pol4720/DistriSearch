"""
Nodes Router - Endpoints para control de nodos
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
router = APIRouter()


def get_docker_service():
    """Dependency injection for docker service."""
    from main import get_docker_service as get_svc
    return get_svc()


def get_cluster_service():
    """Dependency injection for cluster service."""
    from main import get_cluster_service as get_svc
    return get_svc()


@router.get("/containers", summary="Listar contenedores")
async def list_containers():
    """
    Lista todos los contenedores de DistriSearch.
    
    Permite ver qué nodos están corriendo y su estado actual.
    """
    service = get_docker_service()
    if not service or not service.available:
        return {
            "containers": [],
            "docker_available": False,
            "message": "Docker no está disponible. Asegúrese de que el daemon Docker esté corriendo."
        }
    
    containers = service.get_distrisearch_containers()
    return {
        "containers": containers,
        "docker_available": True,
        "total": len(containers),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/stop/{container_name}", summary="Detener nodo")
async def stop_node(container_name: str):
    """
    Detiene un contenedor/nodo de forma controlada.
    
    Simula un apagado graceful del nodo. El cluster debería:
    - Detectar la caída del nodo
    - Redistribuir la carga
    - Si era el líder, iniciar elección de nuevo líder
    
    Args:
        container_name: Nombre o ID del contenedor a detener
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.stop_container(container_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "Nodo detenido. El cluster detectará la caída y tomará acciones correctivas."
        }
    }


@router.post("/start/{container_name}", summary="Iniciar nodo")
async def start_node(container_name: str):
    """
    Inicia un contenedor/nodo que estaba detenido.
    
    Simula la recuperación de un nodo. El cluster debería:
    - Detectar el nuevo nodo
    - Sincronizar datos con el nodo recuperado
    - Añadirlo de vuelta al cluster
    
    Args:
        container_name: Nombre o ID del contenedor a iniciar
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.start_container(container_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "Nodo iniciado. Se sincronizará con el cluster y estará disponible en unos segundos."
        }
    }


@router.post("/restart/{container_name}", summary="Reiniciar nodo")
async def restart_node(container_name: str):
    """
    Reinicia un contenedor/nodo.
    
    Útil para:
    - Aplicar cambios de configuración
    - Simular una recuperación rápida
    - Forzar reconexión al cluster
    
    Args:
        container_name: Nombre o ID del contenedor a reiniciar
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.restart_container(container_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "Nodo reiniciado. Debería reconectarse al cluster automáticamente."
        }
    }


@router.post("/kill/{container_name}", summary="Matar nodo")
async def kill_node(container_name: str, signal: str = Query(default="SIGKILL")):
    """
    Mata un contenedor/nodo de forma brusca.
    
    ⚠️ SIMULACIÓN DE FALLO CATASTRÓFICO ⚠️
    
    Simula un fallo inesperado del nodo sin tiempo para:
    - Cerrar conexiones
    - Guardar estado
    - Notificar al cluster
    
    El cluster debe manejar esto mediante:
    - Detección por timeout de heartbeat
    - Elección de nuevo líder si corresponde
    - Rebalanceo de datos
    
    Args:
        container_name: Nombre o ID del contenedor
        signal: Señal a enviar (default: SIGKILL)
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.kill_container(container_name, signal)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "⚠️ Nodo terminado abruptamente. El cluster detectará el fallo por timeout de heartbeat."
        }
    }


@router.post("/pause/{container_name}", summary="Pausar nodo")
async def pause_node(container_name: str):
    """
    Pausa un contenedor/nodo.
    
    🌐 SIMULACIÓN DE PARTICIÓN DE RED 🌐
    
    Simula que el nodo está vivo pero incomunicado:
    - El proceso sigue corriendo
    - No responde a ninguna petición
    - No envía heartbeats
    
    Útil para probar:
    - Tolerancia a particiones de red
    - Comportamiento con nodos "zombie"
    - Detección de fallos por timeout
    
    Args:
        container_name: Nombre o ID del contenedor a pausar
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.pause_container(container_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "🌐 Nodo pausado (simula partición de red). El nodo está vivo pero no responde."
        }
    }


@router.post("/unpause/{container_name}", summary="Reanudar nodo")
async def unpause_node(container_name: str):
    """
    Reanuda un contenedor/nodo pausado.
    
    Simula la resolución de una partición de red:
    - El nodo vuelve a comunicarse
    - Se sincroniza con el cluster
    - Retoma su rol anterior
    
    Args:
        container_name: Nombre o ID del contenedor a reanudar
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    result = await service.unpause_container(container_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "description": {
            "es": "Nodo reanudado. Se reconectará al cluster y sincronizará su estado."
        }
    }


@router.get("/stats/{container_name}", summary="Estadísticas del nodo")
async def get_node_stats(container_name: str):
    """
    Obtiene estadísticas de un contenedor/nodo.
    
    Incluye:
    - Uso de CPU
    - Uso de memoria
    - Estado del contenedor
    
    Args:
        container_name: Nombre o ID del contenedor
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    stats = service.get_container_stats(container_name)
    
    if not stats:
        raise HTTPException(status_code=404, detail="Contenedor no encontrado")
    
    return stats


@router.get("/logs/{container_name}", summary="Logs del nodo")
async def get_node_logs(container_name: str, tail: int = Query(default=100, ge=1, le=1000)):
    """
    Obtiene los logs de un contenedor/nodo.
    
    Útil para:
    - Diagnosticar problemas
    - Ver eventos de elección de líder
    - Monitorear replicación
    
    Args:
        container_name: Nombre o ID del contenedor
        tail: Número de líneas a obtener (1-1000)
    """
    service = get_docker_service()
    if not service or not service.available:
        raise HTTPException(status_code=503, detail="Docker no disponible")
    
    logs = service.get_container_logs(container_name, tail)
    
    if logs is None:
        raise HTTPException(status_code=404, detail="Contenedor no encontrado")
    
    return {
        "container_name": container_name,
        "logs": logs,
        "lines": tail,
        "timestamp": datetime.utcnow().isoformat()
    }

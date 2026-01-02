"""
Cluster Service - Comunicación con DistriSearch
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ClusterService:
    """
    Servicio para comunicarse con el cluster DistriSearch.
    Proporciona métodos para obtener estado, métricas y ejecutar operaciones.
    """
    
    def __init__(self, base_url: str, docker_service=None):
        """
        Inicializa el servicio de cluster.
        
        Args:
            base_url: URL base del nodo DistriSearch (ej: http://localhost:8000)
            docker_service: Servicio Docker para control de contenedores
        """
        self.base_url = base_url.rstrip('/')
        self.docker_service = docker_service
        self._client = httpx.AsyncClient(timeout=10.0)
        self._cache = {}
        self._cache_ttl = 1.0  # seconds
        
        logger.info(f"ClusterService inicializado con base_url: {base_url}")
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Realiza una petición HTTP al cluster."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP {e.response.status_code}: {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Error de conexión: {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {url} - {e}")
            return None
    
    async def get_cluster_status(self) -> Optional[Dict[str, Any]]:
        """Obtiene el estado completo del cluster."""
        data = await self._request("GET", "/api/v1/cluster/status")
        if data:
            # Añadir información adicional
            data["fetched_at"] = datetime.utcnow().isoformat()
            data["source_url"] = self.base_url
        return data
    
    async def get_nodes(self) -> List[Dict[str, Any]]:
        """Obtiene lista de nodos del cluster."""
        data = await self._request("GET", "/api/v1/cluster/nodes")
        return data if data else []
    
    async def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de un nodo específico."""
        data = await self._request("GET", f"/api/v1/cluster/nodes/{node_id}")
        return data
    
    async def get_health(self) -> Optional[Dict[str, Any]]:
        """Obtiene el health check del sistema."""
        return await self._request("GET", "/api/v1/health/")
    
    async def get_partitions(self) -> Optional[Dict[str, Any]]:
        """Obtiene información de particiones."""
        return await self._request("GET", "/api/v1/cluster/partitions")
    
    async def get_leader_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre el líder actual y el estado de Raft.
        Busca el nodo con role='master' en la lista de nodos.
        """
        cluster_status = await self.get_cluster_status()
        if not cluster_status:
            return {
                "leader_id": None,
                "leader_address": None,
                "term": 0,
                "state": "unknown"
            }
        
        # Buscar el nodo líder (role=master) en la lista de nodos
        nodes = cluster_status.get("nodes", [])
        leader_node = None
        for node in nodes:
            if node.get("role") == "master":
                leader_node = node
                break
        
        if leader_node:
            leader_id = leader_node.get("node_id")
            leader_address = f"{leader_node.get('address', '')}:{leader_node.get('port', '')}"
        else:
            # Fallback a los campos de nivel superior
            leader_id = cluster_status.get("master_node_id")
            leader_address = cluster_status.get("master_address")
        
        return {
            "leader_id": leader_id,
            "leader_address": leader_address,
            "term": cluster_status.get("current_term", 0),
            "state": cluster_status.get("status", "unknown"),
            "nodes": nodes
        }
    
    async def get_replication_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado de replicación del cluster.
        """
        cluster_status = await self.get_cluster_status()
        nodes = cluster_status.get("nodes", []) if cluster_status else []
        
        # Calcular estadísticas de replicación
        total_documents = sum(n.get("document_count", 0) for n in nodes)
        replication_factor = cluster_status.get("replication_factor", 2) if cluster_status else 2
        
        return {
            "replication_factor": replication_factor,
            "total_documents": total_documents,
            "nodes_with_data": len([n for n in nodes if n.get("document_count", 0) > 0]),
            "total_nodes": len(nodes),
            "distribution": [
                {
                    "node_id": n.get("node_id"),
                    "documents": n.get("document_count", 0),
                    "partitions": n.get("partition_count", 0)
                }
                for n in nodes
            ]
        }
    
    async def execute_search(self, query: str) -> Optional[Dict[str, Any]]:
        """Ejecuta una búsqueda en el sistema."""
        return await self._request(
            "POST",
            "/api/v1/search/",
            json={"query": query, "limit": 10}
        )
    
    async def upload_document(self, filename: str, content: bytes) -> Optional[Dict[str, Any]]:
        """Sube un documento al sistema."""
        files = {"file": (filename, content, "application/octet-stream")}
        return await self._request(
            "POST",
            "/api/v1/documents/upload",
            files=files
        )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del sistema para visualización.
        """
        cluster_status = await self.get_cluster_status()
        health = await self.get_health()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "cluster": {},
            "nodes": [],
            "system": {}
        }
        
        if cluster_status:
            metrics["cluster"] = {
                "total_nodes": cluster_status.get("total_nodes", 0),
                "healthy_nodes": cluster_status.get("healthy_nodes", 0),
                "unhealthy_nodes": cluster_status.get("unhealthy_nodes", 0),
                "total_documents": cluster_status.get("total_documents", 0),
                "total_partitions": cluster_status.get("total_partitions", 0),
                "replication_factor": cluster_status.get("replication_factor", 2),
                "status": cluster_status.get("status", "unknown")
            }
            
            for node in cluster_status.get("nodes", []):
                metrics["nodes"].append({
                    "node_id": node.get("node_id"),
                    "status": node.get("status"),
                    "role": node.get("role"),
                    "documents": node.get("document_count", 0),
                    "cpu_usage": node.get("cpu_usage", 0),
                    "memory_usage": node.get("memory_usage", 0),
                    "disk_usage": node.get("disk_usage", 0)
                })
        
        if health:
            metrics["system"] = {
                "uptime_seconds": health.get("uptime_seconds", 0),
                "version": health.get("version", "unknown"),
                "components": health.get("components", [])
            }
        
        return metrics
    
    async def close(self):
        """Cierra las conexiones."""
        await self._client.aclose()

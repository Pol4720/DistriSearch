"""
DistriSearch - Endpoints de Cluster

Endpoints para comunicación entre nodos del cluster:
- Registro de nodos
- Health checks
- Elección de líder
- Replicación
- Routing de queries
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cluster", tags=["cluster"])

# ============================================================================
# Modelos Pydantic para API
# ============================================================================

class NodeRegistration(BaseModel):
    """Datos para registro de un nodo"""
    node_id: str
    ip_address: str
    http_port: int = 8000
    heartbeat_port: int = 5000
    election_port: int = 5001
    can_be_master: bool = True
    document_count: int = 0


class HeartbeatRequest(BaseModel):
    """Request de heartbeat"""
    sender_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    is_master: bool = False


class HeartbeatResponse(BaseModel):
    """Response de heartbeat"""
    node_id: str
    status: str
    is_master: bool
    current_master: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ContentRegistration(BaseModel):
    """Registro de contenido para el índice de ubicación"""
    file_id: str
    filename: str
    node_id: str
    embedding: List[float]  # Vector de embedding
    metadata: Dict[str, Any] = {}


class QueryRequest(BaseModel):
    """Request de búsqueda distribuida"""
    query: str
    limit: int = 10
    search_type: str = "semantic"  # semantic, filename, hybrid


class QueryResponse(BaseModel):
    """Response de búsqueda"""
    results: List[Dict[str, Any]]
    node_id: str
    query_time_ms: float


class ReplicationRequest(BaseModel):
    """Request de replicación"""
    file_id: str
    source_node: str
    is_replica: bool = True
    original_file_id: Optional[str] = None


class ClusterStatus(BaseModel):
    """Estado del cluster"""
    node_id: str
    node_role: str
    is_master: bool
    current_master: Optional[str]
    peers: List[Dict[str, Any]]
    document_count: int
    uptime_seconds: float


# ============================================================================
# Estado global del nodo (se inicializa en startup)
# ============================================================================

class ClusterState:
    """Estado del cluster para este nodo"""
    def __init__(self):
        self.node_id = os.getenv("NODE_ID", "node_1")
        self.node_role = os.getenv("NODE_ROLE", "slave")
        self.is_master = False
        self.current_master: Optional[str] = None
        self.peers: Dict[str, NodeRegistration] = {}
        self.start_time = datetime.utcnow()
        
        # Servicios (se inicializan después)
        self.heartbeat_service = None
        self.election_service = None
        self.location_index = None
        self.load_balancer = None


# Instancia global
cluster_state = ClusterState()


# ============================================================================
# Endpoints de Registro
# ============================================================================

@router.post("/register", response_model=Dict[str, Any])
async def register_node(registration: NodeRegistration):
    """
    Registra un nodo en el cluster.
    Llamado por Slaves al iniciar para unirse al cluster.
    """
    logger.info(f"Registro de nodo: {registration.node_id}")
    
    # Guardar peer
    cluster_state.peers[registration.node_id] = registration
    
    # Si somos master, añadir al índice y balanceador
    if cluster_state.is_master:
        if cluster_state.load_balancer:
            from ..core.models import NodeInfo, NodeStatus
            node_info = NodeInfo(
                node_id=registration.node_id,
                ip_address=registration.ip_address,
                port=registration.http_port,
                status=NodeStatus.ONLINE,
                can_be_master=registration.can_be_master,
                document_count=registration.document_count
            )
            cluster_state.load_balancer.register_node(node_info)
    
    return {
        "status": "registered",
        "node_id": registration.node_id,
        "current_master": cluster_state.current_master,
        "peers_count": len(cluster_state.peers)
    }


@router.delete("/unregister/{node_id}")
async def unregister_node(node_id: str):
    """Elimina un nodo del cluster"""
    if node_id in cluster_state.peers:
        del cluster_state.peers[node_id]
        
        if cluster_state.is_master and cluster_state.load_balancer:
            cluster_state.load_balancer.unregister_node(node_id)
        
        return {"status": "unregistered", "node_id": node_id}
    
    raise HTTPException(status_code=404, detail="Node not found")


# ============================================================================
# Endpoints de Heartbeat
# ============================================================================

@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(request: HeartbeatRequest):
    """
    Endpoint HTTP para heartbeat (alternativo a UDP).
    Útil cuando UDP no está disponible.
    """
    # Actualizar último contacto del peer
    if request.sender_id in cluster_state.peers:
        # TODO: Actualizar timestamp
        pass
    
    return HeartbeatResponse(
        node_id=cluster_state.node_id,
        status="alive",
        is_master=cluster_state.is_master,
        current_master=cluster_state.current_master
    )


@router.get("/health")
async def health_check():
    """Health check básico"""
    return {
        "status": "healthy",
        "node_id": cluster_state.node_id,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health():
    """Health check con métricas detalladas"""
    uptime = (datetime.utcnow() - cluster_state.start_time).total_seconds()
    
    return {
        "status": "healthy",
        "node_id": cluster_state.node_id,
        "node_role": cluster_state.node_role,
        "is_master": cluster_state.is_master,
        "current_master": cluster_state.current_master,
        "peers_count": len(cluster_state.peers),
        "uptime_seconds": uptime,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Endpoints de Ubicación de Contenido
# ============================================================================

@router.post("/register-content")
async def register_content(content: ContentRegistration):
    """
    Registra contenido en el índice de ubicación del Master.
    Llamado por Slaves después de subir un documento.
    """
    if not cluster_state.is_master:
        raise HTTPException(
            status_code=400, 
            detail="This node is not the master"
        )
    
    if not cluster_state.location_index:
        raise HTTPException(
            status_code=503,
            detail="Location index not initialized"
        )
    
    import numpy as np
    embedding = np.array(content.embedding)
    
    cluster_state.location_index.register_document(
        file_id=content.file_id,
        filename=content.filename,
        node_id=content.node_id,
        embedding=embedding,
        metadata=content.metadata
    )
    
    return {
        "status": "registered",
        "file_id": content.file_id,
        "node_id": content.node_id
    }


@router.get("/locate/{file_id}")
async def locate_content(file_id: str):
    """
    Localiza un documento en el cluster.
    Retorna el nodo donde está almacenado.
    """
    if not cluster_state.is_master:
        raise HTTPException(status_code=400, detail="This node is not the master")
    
    if not cluster_state.location_index:
        raise HTTPException(status_code=503, detail="Location index not initialized")
    
    doc = cluster_state.location_index.get_document_location(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "file_id": file_id,
        "filename": doc.filename,
        "node_id": doc.node_id,
        "metadata": doc.metadata
    }


# ============================================================================
# Endpoints de Búsqueda Distribuida
# ============================================================================

@router.post("/query", response_model=QueryResponse)
async def distributed_query(request: QueryRequest):
    """
    Búsqueda distribuida desde el Master.
    Enruta la query a los Slaves más relevantes.
    """
    from ..services.search_service import SearchService
    
    start_time = datetime.utcnow()
    
    # Búsqueda local en este nodo
    search_service = SearchService()
    results = await search_service.search(
        query=request.query,
        limit=request.limit,
        search_type=request.search_type
    )
    
    elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    return QueryResponse(
        results=results,
        node_id=cluster_state.node_id,
        query_time_ms=elapsed
    )


@router.post("/search/distributed")
async def search_distributed(request: QueryRequest):
    """
    Búsqueda distribuida completa (solo en Master).
    Consulta a múltiples Slaves y agrega resultados.
    """
    if not cluster_state.is_master:
        # Si no somos master, forward al master
        if cluster_state.current_master:
            # TODO: Forward request
            pass
        raise HTTPException(status_code=400, detail="This node is not the master")
    
    # TODO: Implementar búsqueda distribuida con QueryRouter
    return {"error": "Not implemented yet"}


# ============================================================================
# Endpoints de Replicación
# ============================================================================

@router.post("/replicate")
async def receive_replica(request: ReplicationRequest):
    """
    Recibe una réplica de documento de otro nodo.
    """
    logger.info(f"Recibiendo réplica: {request.file_id} desde {request.source_node}")
    
    # TODO: Descargar archivo desde source_node y almacenar localmente
    
    return {
        "status": "received",
        "file_id": request.file_id,
        "source_node": request.source_node
    }


# ============================================================================
# Endpoints de Estado del Cluster
# ============================================================================

@router.get("/status", response_model=ClusterStatus)
async def get_cluster_status():
    """Retorna estado completo del cluster desde este nodo"""
    uptime = (datetime.utcnow() - cluster_state.start_time).total_seconds()
    
    peers_list = [
        {
            "node_id": peer.node_id,
            "ip_address": peer.ip_address,
            "http_port": peer.http_port,
            "can_be_master": peer.can_be_master
        }
        for peer in cluster_state.peers.values()
    ]
    
    return ClusterStatus(
        node_id=cluster_state.node_id,
        node_role=cluster_state.node_role,
        is_master=cluster_state.is_master,
        current_master=cluster_state.current_master,
        peers=peers_list,
        document_count=0,  # TODO: Obtener de MongoDB
        uptime_seconds=uptime
    )


@router.get("/nodes")
async def list_nodes():
    """Lista todos los nodos conocidos en el cluster"""
    nodes = [
        {
            "node_id": cluster_state.node_id,
            "is_self": True,
            "is_master": cluster_state.is_master,
            "status": "online"
        }
    ]
    
    for peer in cluster_state.peers.values():
        nodes.append({
            "node_id": peer.node_id,
            "is_self": False,
            "is_master": peer.node_id == cluster_state.current_master,
            "ip_address": peer.ip_address,
            "status": "unknown"  # TODO: Obtener de heartbeat service
        })
    
    return {"nodes": nodes, "total": len(nodes)}


@router.get("/master")
async def get_current_master():
    """Retorna información del master actual"""
    return {
        "current_master": cluster_state.current_master,
        "is_this_node_master": cluster_state.is_master
    }

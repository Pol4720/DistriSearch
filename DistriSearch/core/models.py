"""
DistriSearch Core - Modelos compartidos para el cluster
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import numpy as np


class NodeStatus(Enum):
    """Estados posibles de un nodo"""
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    STARTING = "starting"


class MessageType(Enum):
    """Tipos de mensajes entre nodos del cluster"""
    # Heartbeat
    PING = "PING"
    PONG = "PONG"
    
    # Elección de líder
    ELECTION = "ELECTION"
    ELECTION_OK = "ELECTION_OK"
    COORDINATOR = "COORDINATOR"
    
    # Gestión de documentos
    REGISTER_CONTENT = "REGISTER_CONTENT"
    QUERY_ROUTING = "QUERY_ROUTING"
    REPLICATE = "REPLICATE"
    
    # Sincronización
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"
    
    # Estado
    STATUS_REQUEST = "STATUS_REQUEST"
    STATUS_RESPONSE = "STATUS_RESPONSE"


@dataclass
class NodeInfo:
    """Información de un nodo en el cluster"""
    node_id: str
    ip_address: str
    port: int
    status: NodeStatus = NodeStatus.UNKNOWN
    is_master: bool = False
    can_be_master: bool = True
    document_count: int = 0
    last_seen: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "is_master": self.is_master,
            "can_be_master": self.can_be_master,
            "document_count": self.document_count,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NodeInfo':
        status = data.get("status", "unknown")
        if isinstance(status, str):
            status = NodeStatus(status)
        
        return cls(
            node_id=data["node_id"],
            ip_address=data["ip_address"],
            port=data["port"],
            status=status,
            is_master=data.get("is_master", False),
            can_be_master=data.get("can_be_master", True),
            document_count=data.get("document_count", 0),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else datetime.utcnow(),
            metadata=data.get("metadata", {})
        )


@dataclass
class SlaveProfile:
    """Perfil semántico de un Slave para ubicación de recursos"""
    slave_id: str
    embedding: Optional[np.ndarray] = None  # Vector de embedding agregado
    keywords: List[str] = field(default_factory=list)
    document_count: int = 0
    total_size_bytes: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    load_score: float = 0.0  # 0.0 = sin carga, 1.0 = máxima carga
    
    def to_dict(self) -> Dict:
        return {
            "slave_id": self.slave_id,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "keywords": self.keywords,
            "document_count": self.document_count,
            "total_size_bytes": self.total_size_bytes,
            "last_updated": self.last_updated.isoformat(),
            "load_score": self.load_score
        }


@dataclass 
class ClusterMessage:
    """Mensaje genérico entre nodos del cluster"""
    type: MessageType
    sender_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ClusterMessage':
        return cls(
            type=MessageType(data["type"]),
            sender_id=data["sender_id"],
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow()
        )


@dataclass
class QueryResult:
    """Resultado de una búsqueda"""
    file_id: str
    filename: str
    score: float
    node_id: str
    snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "score": self.score,
            "node_id": self.node_id,
            "snippet": self.snippet,
            "metadata": self.metadata
        }

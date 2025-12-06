"""
DistriSearch Core - Modelos compartidos para el cluster

Este módulo define todos los modelos de datos del sistema:
- Enums: NodeStatus, NodeRole, MessageType, FileType
- Dataclasses: NodeInfo, ClusterMessage, SlaveProfile, QueryResult
- Pydantic: FileMeta, SearchQuery, SearchResult (para API)
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# Importación condicional de numpy (puede no estar disponible en todos los contextos)
try:
    import numpy as np
except ImportError:
    np = None


# ==============================================================================
# ENUMS
# ==============================================================================

class NodeRole(Enum):
    """Roles posibles para un nodo en el cluster"""
    SLAVE = "slave"
    MASTER = "master"


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
    
    # Elección de líder (Algoritmo Bully)
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


class FileType(str, Enum):
    """Tipos de archivo soportados"""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


# ==============================================================================
# DATACLASSES - Modelos internos del cluster
# ==============================================================================

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
    name: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "name": self.name or f"Node {self.node_id}",
            "ip_address": self.ip_address,
            "port": self.port,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "is_master": self.is_master,
            "can_be_master": self.can_be_master,
            "document_count": self.document_count,
            "shared_files_count": self.document_count,  # Alias para compatibilidad
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NodeInfo':
        status = data.get("status", "unknown")
        if isinstance(status, str):
            try:
                status = NodeStatus(status)
            except ValueError:
                status = NodeStatus.UNKNOWN
        
        return cls(
            node_id=data["node_id"],
            ip_address=data.get("ip_address", ""),
            port=data.get("port", 8000),
            status=status,
            is_master=data.get("is_master", False),
            can_be_master=data.get("can_be_master", True),
            document_count=data.get("document_count", data.get("shared_files_count", 0)),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else datetime.utcnow(),
            metadata=data.get("metadata", {}),
            name=data.get("name")
        )


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
class SlaveProfile:
    """Perfil semántico de un Slave para ubicación de recursos"""
    slave_id: str
    embedding: Optional[Any] = None  # np.ndarray cuando numpy está disponible
    keywords: List[str] = field(default_factory=list)
    document_count: int = 0
    total_size_bytes: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    load_score: float = 0.0  # 0.0 = sin carga, 1.0 = máxima carga
    
    def to_dict(self) -> Dict:
        embedding_list = None
        if self.embedding is not None:
            if np is not None and isinstance(self.embedding, np.ndarray):
                embedding_list = self.embedding.tolist()
            elif isinstance(self.embedding, list):
                embedding_list = self.embedding
        
        return {
            "slave_id": self.slave_id,
            "embedding": embedding_list,
            "keywords": self.keywords,
            "document_count": self.document_count,
            "total_size_bytes": self.total_size_bytes,
            "last_updated": self.last_updated.isoformat(),
            "load_score": self.load_score
        }


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


# ==============================================================================
# PYDANTIC MODELS - Modelos para API REST
# ==============================================================================

class FileMetaModel(BaseModel):
    """Metadatos de un archivo (Pydantic para API)"""
    file_id: str
    name: str
    path: str
    size: int  # En bytes
    mime_type: str
    type: FileType
    node_id: str
    last_updated: datetime = Field(default_factory=datetime.now)
    content: Optional[str] = None  # Contenido textual truncado
    content_hash: Optional[str] = None


class NodeInfoModel(BaseModel):
    """Información de nodo (Pydantic para API)"""
    node_id: str
    name: str
    ip_address: str
    port: int
    status: str = "unknown"
    last_seen: datetime = Field(default_factory=datetime.now)
    shared_files_count: int = 0


class SearchQueryModel(BaseModel):
    """Consulta de búsqueda (Pydantic para API)"""
    query: str
    file_type: Optional[FileType] = None
    max_results: int = 50


class SearchResultModel(BaseModel):
    """Resultado de búsqueda (Pydantic para API)"""
    files: List[FileMetaModel]
    total_count: int
    nodes_available: List[NodeInfoModel]


class UserCreate(BaseModel):
    """Creación de usuario"""
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    """Login de usuario"""
    username: str
    password: str


class Token(BaseModel):
    """Token JWT"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Datos del token"""
    username: Optional[str] = None


class DownloadRequest(BaseModel):
    """Solicitud de descarga"""
    file_id: str
    preferred_node_id: Optional[str] = None


class NodeRegistration(BaseModel):
    """Registro dinámico de nodos"""
    node_id: str
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: int = 8080
    shared_folder: Optional[str] = None
    auto_scan: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "node_dynamic_01",
                "name": "Nodo Dinámico 1",
                "port": 8081,
                "shared_folder": "/app/shared",
                "auto_scan": True
            }
        }


# ==============================================================================
# ALIASES para compatibilidad con código existente
# ==============================================================================

# Estos aliases permiten que el código existente siga funcionando
FileMeta = FileMetaModel
SearchQuery = SearchQueryModel
SearchResult = SearchResultModel

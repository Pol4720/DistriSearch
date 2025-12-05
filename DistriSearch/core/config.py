"""
DistriSearch Core - Configuración compartida para todos los nodos del cluster
"""
import os
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum


class NodeRole(Enum):
    """Roles posibles para un nodo en el cluster"""
    SLAVE = "slave"
    MASTER = "master"


@dataclass
class ClusterConfig:
    """Configuración del cluster para este nodo"""
    
    # Identificación del nodo
    node_id: str = field(default_factory=lambda: os.getenv("NODE_ID", "node_1"))
    node_role: NodeRole = field(default_factory=lambda: NodeRole(os.getenv("NODE_ROLE", "slave")))
    
    # Capacidad de ser elegido Master
    master_candidate: bool = field(default_factory=lambda: os.getenv("MASTER_CANDIDATE", "true").lower() == "true")
    
    # Red
    host: str = field(default_factory=lambda: os.getenv("BACKEND_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000")))
    external_ip: Optional[str] = field(default_factory=lambda: os.getenv("EXTERNAL_IP"))
    
    # Peers conocidos
    cluster_peers: List[str] = field(default_factory=lambda: _parse_peers(os.getenv("CLUSTER_PEERS", "")))
    
    # Heartbeat
    heartbeat_interval: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_INTERVAL", "5")))
    heartbeat_timeout: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_TIMEOUT", "15")))
    
    # MongoDB
    mongo_uri: str = field(default_factory=lambda: os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    mongo_dbname: str = field(default_factory=lambda: os.getenv("MONGO_DBNAME", "distrisearch"))
    
    # Replicación
    replication_enabled: bool = field(default_factory=lambda: os.getenv("REPLICATION_ENABLED", "true").lower() == "true")
    replication_factor: int = field(default_factory=lambda: int(os.getenv("REPLICATION_FACTOR", "2")))
    
    # Embeddings para ubicación semántica
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    
    def __post_init__(self):
        """Validaciones post-inicialización"""
        if self.replication_factor < 1:
            self.replication_factor = 1
        if self.heartbeat_timeout <= self.heartbeat_interval:
            self.heartbeat_timeout = self.heartbeat_interval * 3


def _parse_peers(peers_str: str) -> List[str]:
    """Parsea string de peers separados por coma"""
    if not peers_str:
        return []
    return [p.strip() for p in peers_str.split(",") if p.strip()]


# Singleton de configuración
_config: Optional[ClusterConfig] = None


def get_cluster_config() -> ClusterConfig:
    """Obtiene la configuración del cluster (singleton)"""
    global _config
    if _config is None:
        _config = ClusterConfig()
    return _config


def reload_config() -> ClusterConfig:
    """Recarga la configuración desde variables de entorno"""
    global _config
    _config = ClusterConfig()
    return _config

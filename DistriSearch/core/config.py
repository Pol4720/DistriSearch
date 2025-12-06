"""
DistriSearch Core - Configuración compartida para todos los nodos del cluster

Este módulo centraliza toda la configuración del sistema distribuido.
Todas las variables de entorno se documentan aquí.
"""
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class NodeRole(Enum):
    """Roles posibles para un nodo en el cluster"""
    SLAVE = "slave"
    MASTER = "master"


class ConsistencyModel(Enum):
    """Modelos de consistencia soportados"""
    EVENTUAL = "eventual"
    STRONG = "strong"


@dataclass
class NetworkConfig:
    """Configuración de red del nodo"""
    host: str = field(default_factory=lambda: os.getenv("BACKEND_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000")))
    external_ip: Optional[str] = field(default_factory=lambda: os.getenv("EXTERNAL_IP"))
    frontend_port: int = field(default_factory=lambda: int(os.getenv("FRONTEND_PORT", "8501")))
    
    # Puertos UDP para cluster
    heartbeat_port: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_PORT", "5000")))
    election_port: int = field(default_factory=lambda: int(os.getenv("ELECTION_PORT", "5001")))
    
    # Multicast Discovery
    multicast_group: str = field(default_factory=lambda: os.getenv("MULTICAST_GROUP", "239.255.0.1"))
    multicast_port: int = field(default_factory=lambda: int(os.getenv("MULTICAST_PORT", "5353")))
    discovery_interval: int = field(default_factory=lambda: int(os.getenv("DISCOVERY_INTERVAL", "30")))


@dataclass
class HeartbeatConfig:
    """Configuración del servicio de heartbeat"""
    interval: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_INTERVAL", "5")))
    timeout: int = field(default_factory=lambda: int(os.getenv("HEARTBEAT_TIMEOUT", "15")))
    
    def __post_init__(self):
        if self.timeout <= self.interval:
            self.timeout = self.interval * 3


@dataclass
class ElectionConfig:
    """Configuración del servicio de elección de líder (Bully algorithm)"""
    timeout: int = field(default_factory=lambda: int(os.getenv("ELECTION_TIMEOUT", "10")))
    retry_interval: int = field(default_factory=lambda: int(os.getenv("ELECTION_RETRY_INTERVAL", "5")))


@dataclass
class NamingConfig:
    """Configuración del servicio de nombres"""
    cache_ttl: int = field(default_factory=lambda: int(os.getenv("NAMING_CACHE_TTL", "300")))
    max_cache_size: int = field(default_factory=lambda: int(os.getenv("NAMING_MAX_CACHE_SIZE", "1000")))


@dataclass
class ReplicationConfig:
    """Configuración de replicación"""
    enabled: bool = field(default_factory=lambda: os.getenv("REPLICATION_ENABLED", "true").lower() == "true")
    factor: int = field(default_factory=lambda: int(os.getenv("REPLICATION_FACTOR", "2")))
    consistency: ConsistencyModel = field(
        default_factory=lambda: ConsistencyModel(os.getenv("CONSISTENCY_MODEL", "eventual"))
    )
    sync_interval: int = field(default_factory=lambda: int(os.getenv("SYNC_INTERVAL_SECONDS", "60")))
    
    def __post_init__(self):
        if self.factor < 1:
            self.factor = 1


@dataclass
class DatabaseConfig:
    """Configuración de MongoDB"""
    uri: str = field(default_factory=lambda: os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    dbname: str = field(default_factory=lambda: os.getenv("MONGO_DBNAME", "distrisearch"))


@dataclass
class SecurityConfig:
    """Configuración de seguridad"""
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "change-me-in-production"))
    jwt_algorithm: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    token_expire_minutes: int = field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")))
    admin_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ADMIN_API_KEY"))


@dataclass
class EmbeddingConfig:
    """Configuración de embeddings semánticos"""
    model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    dimension: int = 384  # Dimensión del modelo all-MiniLM-L6-v2


@dataclass
class ClusterConfig:
    """Configuración completa del cluster para este nodo"""
    
    # Identificación del nodo
    node_id: str = field(default_factory=lambda: os.getenv("NODE_ID", "node_1"))
    node_role: NodeRole = field(default_factory=lambda: NodeRole(os.getenv("NODE_ROLE", "slave")))
    master_candidate: bool = field(default_factory=lambda: os.getenv("MASTER_CANDIDATE", "true").lower() == "true")
    
    # Peers conocidos (formato: node_id:ip:http_port:heartbeat_port:election_port)
    cluster_peers: List[str] = field(default_factory=lambda: _parse_peers(os.getenv("CLUSTER_PEERS", "")))
    
    # Configuraciones anidadas
    network: NetworkConfig = field(default_factory=NetworkConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    replication: ReplicationConfig = field(default_factory=ReplicationConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    
    # Ambiente
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    
    # Compatibilidad con código existente
    @property
    def host(self) -> str:
        return self.network.host
    
    @property
    def port(self) -> int:
        return self.network.port
    
    @property
    def external_ip(self) -> Optional[str]:
        return self.network.external_ip
    
    @property
    def heartbeat_interval(self) -> int:
        return self.heartbeat.interval
    
    @property
    def heartbeat_timeout(self) -> int:
        return self.heartbeat.timeout
    
    @property
    def mongo_uri(self) -> str:
        return self.database.uri
    
    @property
    def mongo_dbname(self) -> str:
        return self.database.dbname
    
    @property
    def replication_enabled(self) -> bool:
        return self.replication.enabled
    
    @property
    def replication_factor(self) -> int:
        return self.replication.factor
    
    @property
    def embedding_model(self) -> str:
        return self.embedding.model
    
    def get_peer_info(self, peer_str: str) -> Optional[Tuple[str, str, int, int, int]]:
        """
        Parsea información de un peer.
        
        Formato: node_id:ip:http_port:heartbeat_port:election_port
        Retorna: (node_id, ip, http_port, heartbeat_port, election_port)
        """
        parts = peer_str.split(":")
        if len(parts) >= 5:
            return (parts[0], parts[1], int(parts[2]), int(parts[3]), int(parts[4]))
        elif len(parts) >= 3:
            # Formato antiguo: node_id:ip:port
            return (parts[0], parts[1], int(parts[2]), 5000, 5001)
        return None


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


def get_config() -> ClusterConfig:
    """Alias para get_cluster_config()"""
    return get_cluster_config()

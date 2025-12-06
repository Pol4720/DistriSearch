"""
DistriSearch Core - Módulo central compartido
"""
from .config import (
    ClusterConfig, 
    get_cluster_config,
    NetworkConfig,
    HeartbeatConfig,
    ElectionConfig,
    DatabaseConfig,
    ReplicationConfig,
    EmbeddingConfig,
    SecurityConfig,
    NamingConfig,
    NodeRole as ConfigNodeRole,
    ConsistencyModel,
    reload_config,
    get_config
)
from .models import (
    NodeRole,
    NodeStatus,
    MessageType,
    FileType,
    NodeInfo,
    SlaveProfile,
    ClusterMessage,
    QueryResult
)

__all__ = [
    # Config
    "ClusterConfig",
    "get_cluster_config",
    "get_config",
    "reload_config",
    "NetworkConfig",
    "HeartbeatConfig",
    "ElectionConfig",
    "DatabaseConfig",
    "ReplicationConfig",
    "EmbeddingConfig",
    "SecurityConfig",
    "NamingConfig",
    "ConfigNodeRole",
    "ConsistencyModel",
    # Models
    "NodeRole",
    "NodeStatus",
    "MessageType",
    "FileType",
    "NodeInfo",
    "SlaveProfile",
    "ClusterMessage",
    "QueryResult",
]

# Lazy import for messaging to avoid circular imports
def __getattr__(name):
    if name in (
        "serialize_message",
        "deserialize_message",
        "create_heartbeat_ping",
        "create_heartbeat_pong",
        "create_election_message",
        "create_coordinator_message",
        "create_alive_message",
        "create_discovery_announce",
        "create_discovery_request",
        "create_join_cluster_message",
        "create_leave_cluster_message",
        "create_sync_request",
        "create_sync_response",
        "parse_node_info_from_payload"
    ):
        from . import messaging
        return getattr(messaging, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

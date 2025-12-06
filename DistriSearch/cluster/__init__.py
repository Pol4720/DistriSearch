"""
DistriSearch - Módulo de Cluster

Servicios de comunicación y coordinación del cluster distribuido:
- Heartbeat: Monitoreo de nodos via UDP
- Election: Algoritmo Bully para elección de líder
- Discovery: Descubrimiento de nodos via Multicast UDP
- Naming: Sistema de nombres jerárquico
"""

from .heartbeat import HeartbeatService, HeartbeatState
from .election import BullyElection, ElectionState, ElectionConfig
from .discovery import MulticastDiscovery, get_multicast_service
from .naming import HierarchicalNamespace, NamespaceNode, get_namespace, IPCache, get_ip_cache

__all__ = [
    # Heartbeat
    "HeartbeatService",
    "HeartbeatState",
    
    # Election
    "BullyElection",
    "ElectionState",
    "ElectionConfig",
    
    # Discovery
    "MulticastDiscovery",
    "get_multicast_service",
    
    # Naming
    "HierarchicalNamespace",
    "NamespaceNode",
    "get_namespace",
    "IPCache",
    "get_ip_cache",
]

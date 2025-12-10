"""
Coordination module for DistriSearch.

This module contains the cluster coordination components:
- cluster_manager: Manages cluster membership and state
- master_coordinator: Coordinates master node operations
- slave_handler: Handles slave node operations
- service_discovery: Service discovery and DNS integration
"""

from app.distributed.coordination.cluster_manager import (
    ClusterManager,
    ClusterState,
    NodeMembership,
)
from app.distributed.coordination.master_coordinator import (
    MasterCoordinator,
)
from app.distributed.coordination.slave_handler import (
    SlaveHandler,
    SlaveState,
)
from app.distributed.coordination.service_discovery import (
    ServiceDiscovery,
    ServiceEndpoint,
)

__all__ = [
    # Cluster Manager
    "ClusterManager",
    "ClusterState",
    "NodeMembership",
    # Master Coordinator
    "MasterCoordinator",
    # Slave Handler
    "SlaveHandler",
    "SlaveState",
    # Service Discovery
    "ServiceDiscovery",
    "ServiceEndpoint",
]

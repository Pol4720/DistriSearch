"""
Coordination module for DistriSearch.

This module contains the cluster coordination components:
- cluster_manager: Manages cluster membership and state
- master_coordinator: Coordinates master node operations
- slave_handler: Handles slave node operations
- service_discovery: Service discovery and DNS integration
- adaptive_config: Adaptive cluster configuration
- bootstrap: Single-node bootstrap manager
- graceful_degradation: Graceful degradation manager
- adaptive_coordinator: Main adaptive cluster coordinator
"""

from .coordination.cluster_manager import (
    ClusterManager,
    ClusterState,
    NodeMembership,
    NodeRole,
)
from .coordination.master_coordinator import (
    MasterCoordinator,
)
from .coordination.slave_handler import (
    SlaveHandler,
    SlaveState,
)
from .coordination.service_discovery import (
    ServiceDiscovery,
    ServiceEndpoint,
)
from .coordination.adaptive_config import (
    AdaptiveClusterConfig,
    AdaptiveClusterManager,
    OperationMode,
    ConsistencyLevel,
)
from .coordination.bootstrap import (
    SingleNodeBootstrap,
    BootstrapConfig,
    BootstrapPhase,
)
from .coordination.graceful_degradation import (
    GracefulDegradationManager,
    DegradationLevel,
    SystemCapabilities,
)
from .coordination.adaptive_coordinator import (
    AdaptiveClusterCoordinator,
    create_adaptive_coordinator,
)

__all__ = [
    # Cluster Manager
    "ClusterManager",
    "ClusterState",
    "NodeMembership",
    "NodeRole",
    # Master Coordinator
    "MasterCoordinator",
    # Slave Handler
    "SlaveHandler",
    "SlaveState",
    # Service Discovery
    "ServiceDiscovery",
    "ServiceEndpoint",
    # Adaptive Configuration
    "AdaptiveClusterConfig",
    "AdaptiveClusterManager",
    "OperationMode",
    "ConsistencyLevel",
    # Bootstrap
    "SingleNodeBootstrap",
    "BootstrapConfig",
    "BootstrapPhase",
    # Graceful Degradation
    "GracefulDegradationManager",
    "DegradationLevel",
    "SystemCapabilities",
    # Adaptive Coordinator
    "AdaptiveClusterCoordinator",
    "create_adaptive_coordinator",
]

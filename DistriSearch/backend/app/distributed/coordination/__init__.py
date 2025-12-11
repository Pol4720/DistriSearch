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

from app.distributed.coordination.cluster_manager import (
    ClusterManager,
    ClusterState,
    NodeMembership,
    NodeRole,
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
from app.distributed.coordination.adaptive_config import (
    AdaptiveClusterConfig,
    AdaptiveClusterManager,
    OperationMode,
    ConsistencyLevel,
)
from app.distributed.coordination.bootstrap import (
    SingleNodeBootstrap,
    BootstrapConfig,
    BootstrapPhase,
)
from app.distributed.coordination.graceful_degradation import (
    GracefulDegradationManager,
    DegradationLevel,
    SystemCapabilities,
)
from app.distributed.coordination.adaptive_coordinator import (
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

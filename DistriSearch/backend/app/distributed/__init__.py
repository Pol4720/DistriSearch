"""
Distributed module for DistriSearch.

This module contains the distributed systems components:
- consensus: Raft-Lite consensus protocol implementation
- communication: gRPC, REST, WebSocket communication layers
- coordination: Cluster coordination and service discovery
"""

from .consensus import (
    RaftState,
    RaftNode,
    LogEntry,
    LogReplicator,
    LeaderElection,
    StateMachine,
    Command,
    CommandType,
)

from .communication import (
    RESTClient,
    NodeClient,
    MasterClient,
    HeartbeatService,
    HeartbeatClient,
    NodeHeartbeat,
    MessageBroker,
    Message,
    MessageType,
    WebSocketManager,
    WebSocketConnection,
)

from .coordination import (
    ClusterManager,
    ClusterState,
    NodeMembership,
    MasterCoordinator,
    SlaveHandler,
    SlaveState,
    ServiceDiscovery,
    ServiceEndpoint,
)

__all__ = [
    # Consensus
    "RaftState",
    "RaftNode",
    "LogEntry",
    "LogReplicator",
    "LeaderElection",
    "StateMachine",
    "Command",
    "CommandType",
    # Communication
    "RESTClient",
    "NodeClient",
    "MasterClient",
    "HeartbeatService",
    "HeartbeatClient",
    "NodeHeartbeat",
    "MessageBroker",
    "Message",
    "MessageType",
    "WebSocketManager",
    "WebSocketConnection",
    # Coordination
    "ClusterManager",
    "ClusterState",
    "NodeMembership",
    "MasterCoordinator",
    "SlaveHandler",
    "SlaveState",
    "ServiceDiscovery",
    "ServiceEndpoint",
]

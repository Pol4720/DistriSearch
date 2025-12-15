"""
Communication module for DistriSearch.

This module contains the communication layers:
- rest: REST HTTP client for client-slave and slave-master communication
- grpc: gRPC for master-master communication
- websocket: WebSocket for real-time dashboard updates
- heartbeat: Heartbeat mechanism for node health monitoring
"""

from .rest_client import (
    RESTClient,
    NodeClient,
    MasterClient,
    NodeClientPool,
)
from .heartbeat import (
    HeartbeatService,
    HeartbeatClient,
    NodeHeartbeat,
    NodeStatus,
)
from .message_broker import (
    MessageBroker,
    Message,
    MessageType,
)
from .websocket_manager import (
    WebSocketManager,
    WebSocketConnection,
)

__all__ = [
    # REST
    "RESTClient",
    "NodeClient",
    "MasterClient",
    "NodeClientPool",
    # Heartbeat
    "HeartbeatService",
    "HeartbeatClient",
    "NodeHeartbeat",
    "NodeStatus",
    # Message Broker
    "MessageBroker",
    "Message",
    "MessageType",
    # WebSocket
    "WebSocketManager",
    "WebSocketConnection",
]

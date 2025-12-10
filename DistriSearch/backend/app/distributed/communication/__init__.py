"""
Communication module for DistriSearch.

This module contains the communication layers:
- rest: REST HTTP client for client-slave and slave-master communication
- grpc: gRPC for master-master communication
- websocket: WebSocket for real-time dashboard updates
- heartbeat: Heartbeat mechanism for node health monitoring
"""

from app.distributed.communication.rest_client import (
    RESTClient,
    NodeClient,
    MasterClient,
)
from app.distributed.communication.heartbeat import (
    HeartbeatService,
    HeartbeatClient,
    NodeHeartbeat,
)
from app.distributed.communication.message_broker import (
    MessageBroker,
    Message,
    MessageType,
)
from app.distributed.communication.websocket_manager import (
    WebSocketManager,
    WebSocketConnection,
)

__all__ = [
    # REST
    "RESTClient",
    "NodeClient",
    "MasterClient",
    # Heartbeat
    "HeartbeatService",
    "HeartbeatClient",
    "NodeHeartbeat",
    # Message Broker
    "MessageBroker",
    "Message",
    "MessageType",
    # WebSocket
    "WebSocketManager",
    "WebSocketConnection",
]

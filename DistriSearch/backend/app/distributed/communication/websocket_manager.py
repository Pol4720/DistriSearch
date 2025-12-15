"""
WebSocket Manager for real-time communication.

Implements WebSocket connections for:
- Dashboard real-time updates
- Cluster state streaming
- Search result streaming
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Set, Callable, Awaitable
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketEventType(Enum):
    """Types of WebSocket events."""
    
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    
    # Cluster events
    CLUSTER_STATE = "cluster_state"
    NODE_STATUS = "node_status"
    LEADER_CHANGE = "leader_change"
    
    # Document events
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_DELETED = "document_deleted"
    
    # Search events
    SEARCH_STARTED = "search_started"
    SEARCH_RESULT = "search_result"
    SEARCH_COMPLETED = "search_completed"
    
    # Rebalancing events
    REBALANCE_PROGRESS = "rebalance_progress"
    MIGRATION_STATUS = "migration_status"
    
    # System events
    METRICS_UPDATE = "metrics_update"
    LOG_MESSAGE = "log_message"


@dataclass
class WebSocketMessage:
    """
    A WebSocket message.
    
    Attributes:
        type: Event type
        data: Message data
        timestamp: When message was created
        id: Unique message ID
    """
    type: WebSocketEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=WebSocketEventType(data["type"]),
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class WebSocketConnection:
    """
    A WebSocket connection.
    
    Attributes:
        id: Connection ID
        websocket: FastAPI WebSocket object
        client_id: Optional client identifier
        subscriptions: Set of subscribed event types
        connected_at: When connection was established
    """
    id: str
    websocket: WebSocket
    client_id: Optional[str] = None
    subscriptions: Set[WebSocketEventType] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.now)
    
    async def send(self, message: WebSocketMessage):
        """Send message to this connection."""
        try:
            await self.websocket.send_text(message.to_json())
        except Exception as e:
            logger.warning(f"Failed to send to connection {self.id}: {e}")
            raise
    
    async def close(self, code: int = 1000):
        """Close the connection."""
        try:
            await self.websocket.close(code=code)
        except:
            pass


# Callback types
ConnectionCallback = Callable[[WebSocketConnection], Awaitable[None]]
MessageCallback = Callable[[WebSocketConnection, WebSocketMessage], Awaitable[None]]


class WebSocketManager:
    """
    Manager for WebSocket connections.
    
    Features:
    - Multiple concurrent connections
    - Subscription-based message routing
    - Broadcast to all or filtered connections
    - Connection health monitoring
    """
    
    def __init__(
        self,
        ping_interval: float = 30.0,
        max_connections: int = 1000,
    ):
        """
        Initialize WebSocket manager.
        
        Args:
            ping_interval: Ping interval for keep-alive (seconds)
            max_connections: Maximum allowed connections
        """
        self.ping_interval = ping_interval
        self.max_connections = max_connections
        
        # Active connections
        self._connections: Dict[str, WebSocketConnection] = {}
        
        # Callbacks
        self._on_connect: List[ConnectionCallback] = []
        self._on_disconnect: List[ConnectionCallback] = []
        self._on_message: List[MessageCallback] = []
        
        # Ping task
        self._ping_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_connections = 0
        self._total_messages_sent = 0
        self._total_messages_received = 0
        
        logger.info("WebSocketManager initialized")
    
    def on_connect(self, callback: ConnectionCallback):
        """Register connection callback."""
        self._on_connect.append(callback)
    
    def on_disconnect(self, callback: ConnectionCallback):
        """Register disconnection callback."""
        self._on_disconnect.append(callback)
    
    def on_message(self, callback: MessageCallback):
        """Register message callback."""
        self._on_message.append(callback)
    
    async def start(self):
        """Start the WebSocket manager."""
        if self._running:
            return
        
        self._running = True
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("WebSocketManager started")
    
    async def stop(self):
        """Stop the WebSocket manager."""
        self._running = False
        
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._lock:
            for conn in list(self._connections.values()):
                await conn.close()
            self._connections.clear()
        
        logger.info("WebSocketManager stopped")
    
    async def accept(
        self,
        websocket: WebSocket,
        client_id: Optional[str] = None,
    ) -> Optional[WebSocketConnection]:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket object
            client_id: Optional client identifier
            
        Returns:
            WebSocketConnection or None if limit reached
        """
        async with self._lock:
            if len(self._connections) >= self.max_connections:
                logger.warning("Maximum connections reached")
                await websocket.close(code=1013)  # Try again later
                return None
            
            await websocket.accept()
            
            conn = WebSocketConnection(
                id=str(uuid.uuid4()),
                websocket=websocket,
                client_id=client_id,
            )
            
            self._connections[conn.id] = conn
            self._total_connections += 1
        
        logger.info(f"WebSocket connected: {conn.id}")
        
        # Notify callbacks
        for callback in self._on_connect:
            try:
                await callback(conn)
            except Exception as e:
                logger.error(f"Connect callback error: {e}")
        
        # Send welcome message
        await conn.send(WebSocketMessage(
            type=WebSocketEventType.CONNECTED,
            data={"connection_id": conn.id},
        ))
        
        return conn
    
    async def disconnect(self, connection_id: str):
        """
        Disconnect a WebSocket connection.
        
        Args:
            connection_id: Connection ID to disconnect
        """
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
        
        if conn:
            logger.info(f"WebSocket disconnected: {connection_id}")
            
            # Notify callbacks
            for callback in self._on_disconnect:
                try:
                    await callback(conn)
                except Exception as e:
                    logger.error(f"Disconnect callback error: {e}")
            
            await conn.close()
    
    async def handle_connection(self, websocket: WebSocket, client_id: Optional[str] = None):
        """
        Handle a WebSocket connection lifecycle.
        
        Args:
            websocket: FastAPI WebSocket object
            client_id: Optional client identifier
        """
        conn = await self.accept(websocket, client_id)
        if not conn:
            return
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                self._total_messages_received += 1
                
                try:
                    message = WebSocketMessage.from_json(data)
                    
                    # Handle subscription messages
                    if message.type == WebSocketEventType.CONNECTED:
                        # Update subscriptions
                        subs = message.data.get("subscriptions", [])
                        conn.subscriptions = {
                            WebSocketEventType(s) for s in subs
                            if s in [e.value for e in WebSocketEventType]
                        }
                    
                    # Notify callbacks
                    for callback in self._on_message:
                        try:
                            await callback(conn, message)
                        except Exception as e:
                            logger.error(f"Message callback error: {e}")
                            
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {conn.id}")
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error for {conn.id}: {e}")
        finally:
            await self.disconnect(conn.id)
    
    async def send_to(
        self,
        connection_id: str,
        message: WebSocketMessage,
    ) -> bool:
        """
        Send message to specific connection.
        
        Args:
            connection_id: Target connection ID
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        conn = self._connections.get(connection_id)
        if not conn:
            return False
        
        try:
            await conn.send(message)
            self._total_messages_sent += 1
            return True
        except:
            await self.disconnect(connection_id)
            return False
    
    async def broadcast(
        self,
        message: WebSocketMessage,
        exclude: Optional[Set[str]] = None,
    ):
        """
        Broadcast message to all connections.
        
        Args:
            message: Message to broadcast
            exclude: Set of connection IDs to exclude
        """
        exclude = exclude or set()
        
        async with self._lock:
            connections = list(self._connections.values())
        
        failed = []
        for conn in connections:
            if conn.id in exclude:
                continue
            
            # Check subscription
            if conn.subscriptions and message.type not in conn.subscriptions:
                continue
            
            try:
                await conn.send(message)
                self._total_messages_sent += 1
            except:
                failed.append(conn.id)
        
        # Clean up failed connections
        for conn_id in failed:
            await self.disconnect(conn_id)
    
    async def broadcast_to_subscribers(
        self,
        event_type: WebSocketEventType,
        data: Dict[str, Any],
    ):
        """
        Broadcast to connections subscribed to event type.
        
        Args:
            event_type: Event type
            data: Event data
        """
        message = WebSocketMessage(type=event_type, data=data)
        
        async with self._lock:
            connections = list(self._connections.values())
        
        failed = []
        for conn in connections:
            # Send to all if no subscriptions, or if subscribed
            if not conn.subscriptions or event_type in conn.subscriptions:
                try:
                    await conn.send(message)
                    self._total_messages_sent += 1
                except:
                    failed.append(conn.id)
        
        for conn_id in failed:
            await self.disconnect(conn_id)
    
    async def _ping_loop(self):
        """Send periodic pings to keep connections alive."""
        try:
            while self._running:
                await asyncio.sleep(self.ping_interval)
                
                async with self._lock:
                    connections = list(self._connections.values())
                
                failed = []
                for conn in connections:
                    try:
                        await conn.websocket.send_json({"type": "ping"})
                    except:
                        failed.append(conn.id)
                
                for conn_id in failed:
                    await self.disconnect(conn_id)
                    
        except asyncio.CancelledError:
            pass
    
    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get connection by ID."""
        return self._connections.get(connection_id)
    
    def get_connections_by_client(self, client_id: str) -> List[WebSocketConnection]:
        """Get all connections for a client."""
        return [
            conn for conn in self._connections.values()
            if conn.client_id == client_id
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "active_connections": len(self._connections),
            "total_connections": self._total_connections,
            "messages_sent": self._total_messages_sent,
            "messages_received": self._total_messages_received,
            "running": self._running,
        }


class DashboardBroadcaster:
    """
    Helper for broadcasting dashboard updates.
    
    Provides convenient methods for common dashboard events.
    """
    
    def __init__(self, ws_manager: WebSocketManager):
        """
        Initialize broadcaster.
        
        Args:
            ws_manager: WebSocket manager instance
        """
        self.ws_manager = ws_manager
    
    async def cluster_state_update(self, state: Dict[str, Any]):
        """Broadcast cluster state update."""
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.CLUSTER_STATE,
            state,
        )
    
    async def node_status_update(
        self,
        node_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Broadcast node status update."""
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.NODE_STATUS,
            {
                "node_id": node_id,
                "status": status,
                "details": details or {},
            },
        )
    
    async def metrics_update(self, metrics: Dict[str, Any]):
        """Broadcast metrics update."""
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.METRICS_UPDATE,
            metrics,
        )
    
    async def search_progress(
        self,
        search_id: str,
        progress: float,
        partial_results: Optional[List[Dict[str, Any]]] = None,
    ):
        """Broadcast search progress."""
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.SEARCH_RESULT,
            {
                "search_id": search_id,
                "progress": progress,
                "partial_results": partial_results or [],
            },
        )
    
    async def rebalance_progress(
        self,
        progress: float,
        current_operation: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Broadcast rebalance progress."""
        await self.ws_manager.broadcast_to_subscribers(
            WebSocketEventType.REBALANCE_PROGRESS,
            {
                "progress": progress,
                "operation": current_operation,
                "details": details or {},
            },
        )

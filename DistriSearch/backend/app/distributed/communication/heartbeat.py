"""
Heartbeat Service for node health monitoring.

Implements heartbeat mechanism for:
- Node liveness detection
- Failure detection
- Cluster membership tracking
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Node health status."""
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class NodeHeartbeat:
    """
    Heartbeat data from a node.
    
    Attributes:
        node_id: Unique node identifier
        timestamp: When heartbeat was sent
        load: Current load (0.0 - 1.0)
        documents_count: Number of documents stored
        memory_usage: Memory usage percentage
        cpu_usage: CPU usage percentage
        disk_usage: Disk usage percentage
        custom_data: Additional node-specific data
    """
    node_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    load: float = 0.0
    documents_count: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    disk_usage: float = 0.0
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "load": self.load,
            "documents_count": self.documents_count,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "disk_usage": self.disk_usage,
            "custom_data": self.custom_data,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeHeartbeat":
        """Create from dictionary."""
        return cls(
            node_id=data["node_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            load=data.get("load", 0.0),
            documents_count=data.get("documents_count", 0),
            memory_usage=data.get("memory_usage", 0.0),
            cpu_usage=data.get("cpu_usage", 0.0),
            disk_usage=data.get("disk_usage", 0.0),
            custom_data=data.get("custom_data", {}),
        )


@dataclass
class NodeInfo:
    """
    Information about a tracked node.
    
    Attributes:
        node_id: Unique node identifier
        address: Network address
        last_heartbeat: Last received heartbeat
        status: Current status
        missed_heartbeats: Count of missed heartbeats
        first_seen: When node was first seen
    """
    node_id: str
    address: str
    last_heartbeat: Optional[NodeHeartbeat] = None
    status: NodeStatus = NodeStatus.UNKNOWN
    missed_heartbeats: int = 0
    first_seen: datetime = field(default_factory=datetime.now)
    
    def time_since_last_heartbeat(self) -> float:
        """Get seconds since last heartbeat."""
        if self.last_heartbeat is None:
            return float('inf')
        return (datetime.now() - self.last_heartbeat.timestamp).total_seconds()


# Callback types
HeartbeatCallback = Callable[[NodeHeartbeat], Awaitable[None]]
StatusChangeCallback = Callable[[str, NodeStatus, NodeStatus], Awaitable[None]]


class HeartbeatService:
    """
    Service for receiving and processing heartbeats.
    
    Used by master nodes to monitor slave health.
    """
    
    def __init__(
        self,
        heartbeat_interval: float = 5.0,
        suspect_threshold: int = 3,
        dead_threshold: int = 6,
    ):
        """
        Initialize heartbeat service.
        
        Args:
            heartbeat_interval: Expected heartbeat interval (seconds)
            suspect_threshold: Missed heartbeats before suspect
            dead_threshold: Missed heartbeats before dead
        """
        self.heartbeat_interval = heartbeat_interval
        self.suspect_threshold = suspect_threshold
        self.dead_threshold = dead_threshold
        
        # Tracked nodes
        self._nodes: Dict[str, NodeInfo] = {}
        
        # Callbacks
        self._on_heartbeat: List[HeartbeatCallback] = []
        self._on_status_change: List[StatusChangeCallback] = []
        
        # Check task
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("HeartbeatService initialized")
    
    def on_heartbeat(self, callback: HeartbeatCallback):
        """Register heartbeat callback."""
        self._on_heartbeat.append(callback)
    
    def on_status_change(self, callback: StatusChangeCallback):
        """Register status change callback."""
        self._on_status_change.append(callback)
    
    async def start(self):
        """Start the heartbeat check loop."""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("HeartbeatService started")
    
    async def stop(self):
        """Stop the heartbeat check loop."""
        self._running = False
        
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("HeartbeatService stopped")
    
    async def register_node(self, node_id: str, address: str):
        """
        Register a node for heartbeat tracking.
        
        Args:
            node_id: Node identifier
            address: Node network address
        """
        async with self._lock:
            if node_id not in self._nodes:
                self._nodes[node_id] = NodeInfo(
                    node_id=node_id,
                    address=address,
                    status=NodeStatus.UNKNOWN,
                )
                logger.info(f"Registered node {node_id} for heartbeat tracking")
    
    async def unregister_node(self, node_id: str):
        """
        Unregister a node from heartbeat tracking.
        
        Args:
            node_id: Node identifier
        """
        async with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info(f"Unregistered node {node_id}")
    
    async def receive_heartbeat(self, heartbeat: NodeHeartbeat):
        """
        Process received heartbeat.
        
        Args:
            heartbeat: Received heartbeat data
        """
        async with self._lock:
            node_id = heartbeat.node_id
            
            if node_id not in self._nodes:
                # Auto-register unknown node
                self._nodes[node_id] = NodeInfo(
                    node_id=node_id,
                    address=heartbeat.custom_data.get("address", "unknown"),
                )
            
            node = self._nodes[node_id]
            old_status = node.status
            
            # Update node info
            node.last_heartbeat = heartbeat
            node.missed_heartbeats = 0
            node.status = NodeStatus.HEALTHY
            
            # Notify status change
            if old_status != NodeStatus.HEALTHY:
                await self._notify_status_change(node_id, old_status, NodeStatus.HEALTHY)
        
        # Notify callbacks
        for callback in self._on_heartbeat:
            try:
                await callback(heartbeat)
            except Exception as e:
                logger.error(f"Heartbeat callback error: {e}")
    
    async def _check_loop(self):
        """Periodically check for missed heartbeats."""
        try:
            while self._running:
                await self._check_heartbeats()
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat check error: {e}")
    
    async def _check_heartbeats(self):
        """Check all nodes for missed heartbeats."""
        async with self._lock:
            for node_id, node in self._nodes.items():
                time_since = node.time_since_last_heartbeat()
                missed = int(time_since / self.heartbeat_interval)
                
                old_status = node.status
                
                if missed >= self.dead_threshold:
                    node.status = NodeStatus.DEAD
                    node.missed_heartbeats = missed
                elif missed >= self.suspect_threshold:
                    node.status = NodeStatus.SUSPECT
                    node.missed_heartbeats = missed
                
                if node.status != old_status:
                    await self._notify_status_change(node_id, old_status, node.status)
    
    async def _notify_status_change(
        self,
        node_id: str,
        old_status: NodeStatus,
        new_status: NodeStatus,
    ):
        """Notify callbacks of status change."""
        logger.info(
            f"Node {node_id} status changed: {old_status.value} -> {new_status.value}"
        )
        
        for callback in self._on_status_change:
            try:
                await callback(node_id, old_status, new_status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")
    
    def get_node_status(self, node_id: str) -> Optional[NodeStatus]:
        """Get current status of a node."""
        node = self._nodes.get(node_id)
        return node.status if node else None
    
    def get_healthy_nodes(self) -> List[str]:
        """Get list of healthy node IDs."""
        return [
            node_id for node_id, node in self._nodes.items()
            if node.status == NodeStatus.HEALTHY
        ]
    
    def get_all_nodes(self) -> Dict[str, NodeInfo]:
        """Get all tracked nodes."""
        return self._nodes.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status for monitoring."""
        status_counts = {status: 0 for status in NodeStatus}
        for node in self._nodes.values():
            status_counts[node.status] += 1
        
        return {
            "total_nodes": len(self._nodes),
            "healthy": status_counts[NodeStatus.HEALTHY],
            "suspect": status_counts[NodeStatus.SUSPECT],
            "dead": status_counts[NodeStatus.DEAD],
            "unknown": status_counts[NodeStatus.UNKNOWN],
            "running": self._running,
        }


class HeartbeatClient:
    """
    Client for sending heartbeats to master.
    
    Used by slave nodes to report their health.
    """
    
    def __init__(
        self,
        node_id: str,
        master_url: str,
        interval: float = 5.0,
        stats_collector: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """
        Initialize heartbeat client.
        
        Args:
            node_id: This node's ID
            master_url: Master's heartbeat endpoint URL
            interval: Heartbeat interval in seconds
            stats_collector: Function to collect node stats
        """
        self.node_id = node_id
        self.master_url = master_url
        self.interval = interval
        self.stats_collector = stats_collector
        
        # Heartbeat task
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self._sent_count = 0
        self._failed_count = 0
        
        logger.info(f"HeartbeatClient initialized for node {node_id}")
    
    async def start(self):
        """Start sending heartbeats."""
        if self._running:
            return
        
        self._running = True
        self._session = aiohttp.ClientSession()
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("HeartbeatClient started")
    
    async def stop(self):
        """Stop sending heartbeats."""
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._session and not self._session.closed:
            await self._session.close()
        
        logger.info("HeartbeatClient stopped")
    
    async def _heartbeat_loop(self):
        """Send heartbeats periodically."""
        try:
            while self._running:
                await self._send_heartbeat()
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    async def _send_heartbeat(self):
        """Send a single heartbeat."""
        try:
            # Collect stats
            stats = {}
            if self.stats_collector:
                try:
                    stats = self.stats_collector()
                except Exception as e:
                    logger.warning(f"Stats collection error: {e}")
            
            # Create heartbeat
            heartbeat = NodeHeartbeat(
                node_id=self.node_id,
                load=stats.get("load", 0.0),
                documents_count=stats.get("documents_count", 0),
                memory_usage=stats.get("memory_usage", 0.0),
                cpu_usage=stats.get("cpu_usage", 0.0),
                disk_usage=stats.get("disk_usage", 0.0),
                custom_data=stats,
            )
            
            # Send heartbeat
            async with self._session.post(
                self.master_url,
                json=heartbeat.to_dict(),
                timeout=aiohttp.ClientTimeout(total=5.0),
            ) as response:
                if response.status == 200:
                    self._sent_count += 1
                else:
                    self._failed_count += 1
                    logger.warning(
                        f"Heartbeat failed with status {response.status}"
                    )
                    
        except Exception as e:
            self._failed_count += 1
            logger.warning(f"Failed to send heartbeat: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "node_id": self.node_id,
            "sent_count": self._sent_count,
            "failed_count": self._failed_count,
            "running": self._running,
        }


# Import for type hints
import aiohttp

# -*- coding: utf-8 -*-
"""
Failure Detector - Detects node failures via heartbeat monitoring.

Uses configurable timeout and threshold for failure detection.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Node health status."""
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    FAILED = "failed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


@dataclass
class NodeHealth:
    """Health information for a node."""
    node_id: str
    status: NodeStatus = NodeStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    last_failure: Optional[datetime] = None
    recovery_attempts: int = 0
    latency_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    @property
    def time_since_heartbeat(self) -> Optional[timedelta]:
        if self.last_heartbeat:
            return datetime.utcnow() - self.last_heartbeat
        return None
    
    @property
    def is_healthy(self) -> bool:
        return self.status == NodeStatus.HEALTHY


@dataclass
class FailureEvent:
    """Represents a node failure event."""
    node_id: str
    detected_at: datetime
    last_healthy: Optional[datetime]
    failure_type: str  # "timeout", "error", "explicit"
    details: str = ""
    
    @property
    def downtime(self) -> Optional[timedelta]:
        if self.last_healthy:
            return self.detected_at - self.last_healthy
        return None


class FailureDetector:
    """
    Detects node failures using heartbeat monitoring.
    
    Features:
    - Configurable heartbeat interval and timeout
    - Suspect state before declaring failure
    - Callback on failure detection
    - Recovery detection
    """
    
    def __init__(
        self,
        heartbeat_interval_sec: float = 5.0,
        failure_timeout_sec: float = 15.0,
        suspect_threshold: int = 2,
        failure_threshold: int = 3,
        on_failure: Optional[Callable[[FailureEvent], Awaitable[None]]] = None,
        on_recovery: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        Initialize failure detector.
        
        Args:
            heartbeat_interval_sec: How often to check heartbeats
            failure_timeout_sec: Time without heartbeat to consider failure
            suspect_threshold: Missed heartbeats before suspect status
            failure_threshold: Missed heartbeats before failure status
            on_failure: Callback when node fails
            on_recovery: Callback when node recovers
        """
        self.heartbeat_interval = heartbeat_interval_sec
        self.failure_timeout = failure_timeout_sec
        self.suspect_threshold = suspect_threshold
        self.failure_threshold = failure_threshold
        self._on_failure = on_failure
        self._on_recovery = on_recovery
        
        # State
        self._nodes: Dict[str, NodeHealth] = {}
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._failed_nodes: Set[str] = set()
        
        # History
        self._failure_history: List[FailureEvent] = []
    
    def register_node(self, node_id: str, metadata: Optional[Dict] = None) -> None:
        """
        Register a node for monitoring.
        
        Args:
            node_id: Node identifier
            metadata: Optional node metadata
        """
        self._nodes[node_id] = NodeHealth(
            node_id=node_id,
            status=NodeStatus.UNKNOWN,
            metadata=metadata or {}
        )
        logger.info(f"Registered node for monitoring: {node_id}")
    
    def unregister_node(self, node_id: str) -> None:
        """Remove a node from monitoring."""
        self._nodes.pop(node_id, None)
        self._failed_nodes.discard(node_id)
        logger.info(f"Unregistered node: {node_id}")
    
    def record_heartbeat(
        self,
        node_id: str,
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a heartbeat from a node.
        
        Args:
            node_id: Node that sent heartbeat
            latency_ms: Response latency
            metadata: Optional updated metadata
        """
        if node_id not in self._nodes:
            self.register_node(node_id, metadata)
        
        health = self._nodes[node_id]
        was_failed = health.status == NodeStatus.FAILED
        
        health.last_heartbeat = datetime.utcnow()
        health.consecutive_failures = 0
        health.latency_ms = latency_ms
        health.status = NodeStatus.HEALTHY
        
        if metadata:
            health.metadata.update(metadata)
        
        # Check for recovery
        if was_failed:
            self._failed_nodes.discard(node_id)
            health.status = NodeStatus.RECOVERING
            logger.info(f"Node {node_id} recovered")
            
            if self._on_recovery:
                asyncio.create_task(self._on_recovery(node_id))
    
    def record_failure(self, node_id: str, error: str = "") -> None:
        """
        Record a failed health check for a node.
        
        Args:
            node_id: Node that failed check
            error: Error details
        """
        if node_id not in self._nodes:
            return
        
        health = self._nodes[node_id]
        health.consecutive_failures += 1
        health.last_failure = datetime.utcnow()
        
        # Update status based on consecutive failures
        if health.consecutive_failures >= self.failure_threshold:
            if health.status != NodeStatus.FAILED:
                self._mark_failed(health, "threshold", error)
        elif health.consecutive_failures >= self.suspect_threshold:
            health.status = NodeStatus.SUSPECT
            logger.warning(f"Node {node_id} is suspect ({health.consecutive_failures} failures)")
    
    def _mark_failed(
        self,
        health: NodeHealth,
        failure_type: str,
        details: str = ""
    ) -> None:
        """Mark a node as failed."""
        health.status = NodeStatus.FAILED
        self._failed_nodes.add(health.node_id)
        
        event = FailureEvent(
            node_id=health.node_id,
            detected_at=datetime.utcnow(),
            last_healthy=health.last_heartbeat,
            failure_type=failure_type,
            details=details
        )
        
        self._failure_history.append(event)
        logger.error(f"Node {health.node_id} marked as FAILED: {failure_type}")
        
        if self._on_failure:
            asyncio.create_task(self._on_failure(event))
    
    async def start_monitoring(self) -> None:
        """Start the monitoring loop."""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started failure detector monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped failure detector monitoring")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._is_running:
            try:
                self._check_all_nodes()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.heartbeat_interval)
    
    def _check_all_nodes(self) -> None:
        """Check all nodes for timeouts."""
        now = datetime.utcnow()
        timeout = timedelta(seconds=self.failure_timeout)
        
        for health in self._nodes.values():
            if health.status == NodeStatus.FAILED:
                continue
            
            if health.last_heartbeat is None:
                # Never received heartbeat
                health.consecutive_failures += 1
                if health.consecutive_failures >= self.failure_threshold:
                    self._mark_failed(health, "no_heartbeat", "Never received heartbeat")
                continue
            
            time_since = now - health.last_heartbeat
            
            if time_since > timeout:
                health.consecutive_failures += 1
                
                if health.consecutive_failures >= self.failure_threshold:
                    self._mark_failed(
                        health,
                        "timeout",
                        f"No heartbeat for {time_since.total_seconds():.1f}s"
                    )
                elif health.consecutive_failures >= self.suspect_threshold:
                    health.status = NodeStatus.SUSPECT
    
    def get_node_health(self, node_id: str) -> Optional[NodeHealth]:
        """Get health info for a node."""
        return self._nodes.get(node_id)
    
    def get_all_health(self) -> Dict[str, NodeHealth]:
        """Get health info for all nodes."""
        return dict(self._nodes)
    
    def get_healthy_nodes(self) -> List[str]:
        """Get list of healthy node IDs."""
        return [
            node_id for node_id, health in self._nodes.items()
            if health.is_healthy
        ]
    
    def get_failed_nodes(self) -> List[str]:
        """Get list of failed node IDs."""
        return list(self._failed_nodes)
    
    def get_suspect_nodes(self) -> List[str]:
        """Get list of suspect node IDs."""
        return [
            node_id for node_id, health in self._nodes.items()
            if health.status == NodeStatus.SUSPECT
        ]
    
    def is_node_healthy(self, node_id: str) -> bool:
        """Check if a specific node is healthy."""
        health = self._nodes.get(node_id)
        return health is not None and health.is_healthy
    
    def get_failure_history(self, limit: int = 50) -> List[FailureEvent]:
        """Get recent failure events."""
        return self._failure_history[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get detector statistics."""
        status_counts = {}
        for health in self._nodes.values():
            status = health.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "is_running": self._is_running,
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(self.get_healthy_nodes()),
            "failed_nodes": len(self._failed_nodes),
            "suspect_nodes": len(self.get_suspect_nodes()),
            "status_distribution": status_counts,
            "total_failures": len(self._failure_history),
            "config": {
                "heartbeat_interval_sec": self.heartbeat_interval,
                "failure_timeout_sec": self.failure_timeout,
                "failure_threshold": self.failure_threshold
            }
        }

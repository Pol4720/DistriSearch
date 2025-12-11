# -*- coding: utf-8 -*-
"""
Adaptive Cluster Coordinator

Integrates all adaptive components for dynamic cluster management.
This module coordinates:
- Graceful degradation manager
- Adaptive configuration
- Single-node bootstrap
- Partition tolerance

This serves as the main entry point for the adaptive cluster functionality.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime

from .cluster_manager import ClusterManager, ClusterState, NodeRole, NodeMembership
from .adaptive_config import (
    AdaptiveClusterConfig,
    AdaptiveClusterManager,
    OperationMode,
    ConsistencyLevel
)
from .bootstrap import SingleNodeBootstrap, BootstrapConfig, BootstrapPhase
from .graceful_degradation import (
    GracefulDegradationManager,
    DegradationLevel,
    SystemCapabilities
)

logger = logging.getLogger(__name__)


@dataclass 
class AdaptiveClusterConfig:
    """Configuration for adaptive cluster coordinator."""
    node_id: str
    node_address: str
    target_nodes: int = 3
    target_replication: int = 2
    seed_nodes: List[str] = None
    allow_single_node: bool = True
    auto_bootstrap: bool = True
    
    def __post_init__(self):
        if self.seed_nodes is None:
            self.seed_nodes = []


class AdaptiveClusterCoordinator:
    """
    Main coordinator for adaptive cluster behavior.
    
    This class integrates all the adaptive components and provides
    a unified interface for managing a cluster that can:
    - Start with a single node
    - Grow incrementally to target size
    - Handle partitions gracefully
    - Degrade gracefully under failures
    - Recover automatically
    """
    
    def __init__(
        self,
        config: AdaptiveClusterConfig,
        cluster_manager: Optional[ClusterManager] = None
    ):
        """
        Initialize adaptive cluster coordinator.
        
        Args:
            config: Adaptive cluster configuration
            cluster_manager: Existing cluster manager (optional)
        """
        self.config = config
        self._cluster_manager = cluster_manager
        
        # Initialize graceful degradation manager
        self._degradation_manager = GracefulDegradationManager(
            node_id=config.node_id,
            node_address=config.node_address,
            target_nodes=config.target_nodes,
            target_replication=config.target_replication,
            seed_nodes=config.seed_nodes
        )
        
        # State
        self._is_running = False
        self._start_time: Optional[datetime] = None
        
        # Callbacks
        self._on_ready: List[Callable[[], Awaitable[None]]] = []
        self._on_state_change: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        
        # Register degradation callbacks
        self._degradation_manager.on_degradation_change(self._on_degradation_change)
    
    @property
    def is_ready(self) -> bool:
        """Check if cluster is ready for operations."""
        return self._is_running
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._degradation_manager._bootstrap.is_leader
    
    @property
    def cluster_size(self) -> int:
        """Get current cluster size."""
        return self._degradation_manager._bootstrap.cluster_size
    
    @property
    def degradation_level(self) -> DegradationLevel:
        """Get current degradation level."""
        return self._degradation_manager._degradation_level
    
    @property
    def capabilities(self) -> SystemCapabilities:
        """Get current system capabilities."""
        return self._degradation_manager._capabilities
    
    def on_ready(self, callback: Callable[[], Awaitable[None]]):
        """Register callback for when cluster is ready."""
        self._on_ready.append(callback)
    
    def on_state_change(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Register state change callback."""
        self._on_state_change.append(callback)
    
    async def start(self) -> Dict[str, Any]:
        """
        Start the adaptive cluster coordinator.
        
        This will:
        1. Start in single-node mode if no peers available
        2. Attempt to discover and join existing cluster
        3. Initialize graceful degradation
        4. Begin monitoring and adapting
        
        Returns:
            Startup status
        """
        self._start_time = datetime.now()
        
        logger.info(f"Starting adaptive cluster coordinator for node {self.config.node_id}")
        
        # Start degradation manager (which handles bootstrap)
        result = await self._degradation_manager.start()
        
        self._is_running = True
        
        # Notify ready callbacks
        for callback in self._on_ready:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Ready callback error: {e}")
        
        logger.info(f"Adaptive cluster coordinator started: {result}")
        
        return {
            "status": "started",
            "node_id": self.config.node_id,
            "is_leader": self.is_leader,
            "cluster_size": self.cluster_size,
            "degradation_level": self.degradation_level.name,
            "capabilities": self.capabilities.to_dict(),
            "startup_time_ms": (datetime.now() - self._start_time).total_seconds() * 1000
        }
    
    async def stop(self):
        """Stop the adaptive cluster coordinator."""
        self._is_running = False
        await self._degradation_manager.stop()
        logger.info("Adaptive cluster coordinator stopped")
    
    async def add_node(self, node_id: str, node_address: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add a new node to the cluster.
        
        Args:
            node_id: New node's ID
            node_address: New node's address
            metadata: Optional metadata
            
        Returns:
            Result of node addition
        """
        if not self.is_leader:
            return {
                "success": False,
                "error": "Not the leader",
                "leader_id": self._degradation_manager._bootstrap.leader_id
            }
        
        node_info = {
            "address": node_address,
            "metadata": metadata or {},
            "joined_at": datetime.now().isoformat()
        }
        
        result = await self._degradation_manager.node_joined(node_id, node_info)
        
        # Also add to cluster manager if available
        if self._cluster_manager:
            await self._cluster_manager.add_node(
                node_id, 
                node_address, 
                NodeRole.SLAVE,
                metadata
            )
        
        return {
            "success": True,
            "node_id": node_id,
            "cluster_size": self.cluster_size,
            "status": result
        }
    
    async def remove_node(self, node_id: str, reason: str = "manual") -> Dict[str, Any]:
        """
        Remove a node from the cluster.
        
        Args:
            node_id: Node to remove
            reason: Reason for removal
            
        Returns:
            Result of node removal
        """
        result = await self._degradation_manager.node_left(node_id, reason)
        
        # Also remove from cluster manager if available
        if self._cluster_manager:
            await self._cluster_manager.remove_node(node_id)
        
        return {
            "success": True,
            "node_id": node_id,
            "cluster_size": self.cluster_size,
            "status": result
        }
    
    async def handle_node_failure(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node failure.
        
        Args:
            node_id: Failed node
            
        Returns:
            Updated status
        """
        result = await self._degradation_manager.node_failed(node_id)
        
        logger.warning(f"Node {node_id} failed, degradation level: {self.degradation_level.name}")
        
        return {
            "node_id": node_id,
            "handled": True,
            "status": result
        }
    
    async def handle_node_recovery(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node recovery.
        
        Args:
            node_id: Recovered node
            
        Returns:
            Updated status
        """
        result = await self._degradation_manager.node_recovered(node_id)
        
        logger.info(f"Node {node_id} recovered, degradation level: {self.degradation_level.name}")
        
        return {
            "node_id": node_id,
            "handled": True,
            "status": result
        }
    
    def check_operation(self, operation: str) -> Dict[str, Any]:
        """
        Check if an operation is allowed in current state.
        
        Args:
            operation: Operation type (write, read, replicate, etc.)
            
        Returns:
            Check result with allowed status
        """
        return self._degradation_manager.check_operation_allowed(operation)
    
    async def _on_degradation_change(
        self, 
        level: DegradationLevel, 
        capabilities: SystemCapabilities
    ):
        """Handle degradation level change."""
        logger.info(f"Degradation changed to {level.name}")
        
        state = {
            "degradation_level": level.name,
            "capabilities": capabilities.to_dict(),
            "cluster_size": self.cluster_size,
            "is_leader": self.is_leader,
            "timestamp": datetime.now().isoformat()
        }
        
        # Notify state change callbacks
        for callback in self._on_state_change:
            try:
                await callback(state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive coordinator status."""
        uptime = None
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        
        return {
            "node_id": self.config.node_id,
            "is_running": self._is_running,
            "is_leader": self.is_leader,
            "cluster_size": self.cluster_size,
            "target_size": self.config.target_nodes,
            "degradation_level": self.degradation_level.name,
            "capabilities": self.capabilities.to_dict(),
            "uptime_seconds": uptime,
            "degradation_status": self._degradation_manager.get_status()
        }
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """Get cluster health summary."""
        caps = self.capabilities
        
        # Calculate health score (0-100)
        health_score = 100
        
        if self.degradation_level == DegradationLevel.CRITICAL:
            health_score = 10
        elif self.degradation_level == DegradationLevel.SIGNIFICANT:
            health_score = 30
        elif self.degradation_level == DegradationLevel.MODERATE:
            health_score = 60
        elif self.degradation_level == DegradationLevel.MINIMAL:
            health_score = 85
        
        # Adjust for capabilities
        if not caps.can_write:
            health_score = min(health_score, 20)
        if not caps.strong_consistency_available:
            health_score = min(health_score, 70)
        
        return {
            "health_score": health_score,
            "degradation_level": self.degradation_level.name,
            "node_count": self.cluster_size,
            "target_nodes": self.config.target_nodes,
            "fault_tolerance": caps.fault_tolerance_level,
            "can_write": caps.can_write,
            "can_read": caps.can_read,
            "strong_consistency": caps.strong_consistency_available,
            "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 40 else "critical"
        }


# Factory function for easy creation
def create_adaptive_coordinator(
    node_id: str,
    node_address: str,
    target_nodes: int = 3,
    target_replication: int = 2,
    seed_nodes: Optional[List[str]] = None,
    cluster_manager: Optional[ClusterManager] = None
) -> AdaptiveClusterCoordinator:
    """
    Create an adaptive cluster coordinator.
    
    Args:
        node_id: This node's ID
        node_address: This node's address
        target_nodes: Target cluster size
        target_replication: Target replication factor
        seed_nodes: Seed nodes for discovery
        cluster_manager: Existing cluster manager
        
    Returns:
        Configured AdaptiveClusterCoordinator
    """
    config = AdaptiveClusterConfig(
        node_id=node_id,
        node_address=node_address,
        target_nodes=target_nodes,
        target_replication=target_replication,
        seed_nodes=seed_nodes or []
    )
    
    return AdaptiveClusterCoordinator(config, cluster_manager)

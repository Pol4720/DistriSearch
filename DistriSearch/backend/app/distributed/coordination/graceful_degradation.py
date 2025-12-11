# -*- coding: utf-8 -*-
"""
Graceful Degradation Manager

Coordinates all adaptive components to ensure the system degrades
gracefully under various failure scenarios while maintaining availability.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .adaptive_config import (
    AdaptiveClusterConfig,
    AdaptiveClusterManager,
    OperationMode,
    ConsistencyLevel
)
from .bootstrap import SingleNodeBootstrap, BootstrapConfig, BootstrapPhase

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    """System degradation levels."""
    NONE = 0          # Full functionality
    MINIMAL = 1       # Slight reduction in redundancy
    MODERATE = 2      # Reduced replication/quorum
    SIGNIFICANT = 3   # Single-node or minority partition
    CRITICAL = 4      # Read-only or severely limited


@dataclass
class SystemCapabilities:
    """Current system capabilities based on degradation level."""
    can_write: bool = True
    can_read: bool = True
    can_replicate: bool = True
    can_rebalance: bool = True
    strong_consistency_available: bool = True
    fault_tolerance_level: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_write": self.can_write,
            "can_read": self.can_read,
            "can_replicate": self.can_replicate,
            "can_rebalance": self.can_rebalance,
            "strong_consistency_available": self.strong_consistency_available,
            "fault_tolerance_level": self.fault_tolerance_level
        }


class GracefulDegradationManager:
    """
    Manages graceful degradation of the system.
    
    Ensures the system:
    - Always remains available (even with 1 node)
    - Adjusts capabilities based on available resources
    - Provides clear status about current limitations
    - Automatically recovers when resources become available
    """
    
    def __init__(
        self,
        node_id: str,
        node_address: str,
        target_nodes: int = 3,
        target_replication: int = 2,
        seed_nodes: Optional[List[str]] = None
    ):
        """
        Initialize degradation manager.
        
        Args:
            node_id: This node's ID
            node_address: This node's address
            target_nodes: Target cluster size
            target_replication: Target replication factor
            seed_nodes: Seed nodes for discovery
        """
        self.node_id = node_id
        self.node_address = node_address
        
        # Initialize components
        self._cluster_config = AdaptiveClusterConfig(
            target_nodes=target_nodes,
            target_replication_factor=target_replication,
            target_quorum_size=(target_nodes // 2) + 1
        )
        
        self._cluster_manager = AdaptiveClusterManager(
            config=self._cluster_config,
            node_id=node_id
        )
        
        self._bootstrap = SingleNodeBootstrap(
            config=BootstrapConfig(
                node_id=node_id,
                node_address=node_address,
                seed_nodes=seed_nodes or [],
                allow_single_node=True,
                auto_promote_to_leader=True
            ),
            on_become_leader=self._on_become_leader,
            on_join_cluster=self._on_join_cluster,
            on_cluster_formed=self._on_cluster_formed
        )
        
        # Current state
        self._degradation_level = DegradationLevel.SIGNIFICANT  # Start degraded
        self._capabilities = SystemCapabilities(
            can_write=True,
            can_read=True,
            can_replicate=False,  # Can't replicate with 1 node
            can_rebalance=False,
            strong_consistency_available=False,
            fault_tolerance_level=0
        )
        
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_degradation_change: List[Callable[[DegradationLevel, SystemCapabilities], Awaitable[None]]] = []
    
    def on_degradation_change(
        self, 
        callback: Callable[[DegradationLevel, SystemCapabilities], Awaitable[None]]
    ):
        """Register degradation change callback."""
        self._on_degradation_change.append(callback)
    
    async def start(self) -> Dict[str, Any]:
        """
        Start the degradation manager and bootstrap process.
        
        Returns:
            Initial system status
        """
        self._is_running = True
        
        # Start bootstrap
        bootstrap_result = await self._bootstrap.start()
        
        # Update degradation based on bootstrap result
        await self._update_degradation_level()
        
        # Start monitoring
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"Graceful degradation manager started: {self._degradation_level.name}")
        
        return {
            "node_id": self.node_id,
            "bootstrap": bootstrap_result,
            "degradation_level": self._degradation_level.name,
            "capabilities": self._capabilities.to_dict()
        }
    
    async def stop(self):
        """Stop the degradation manager."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        await self._bootstrap.stop()
        
        logger.info("Graceful degradation manager stopped")
    
    async def node_joined(self, node_id: str, node_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a node joining.
        
        Args:
            node_id: New node ID
            node_info: Node information
            
        Returns:
            Updated status
        """
        # Update cluster manager
        self._cluster_manager.node_joined(node_id, node_info)
        
        # Update bootstrap
        if self._bootstrap.is_leader:
            await self._bootstrap.handle_node_join(node_id, node_info.get("address", ""))
        
        # Update degradation
        await self._update_degradation_level()
        
        return self.get_status()
    
    async def node_left(self, node_id: str, reason: str = "unknown") -> Dict[str, Any]:
        """
        Handle a node leaving.
        
        Args:
            node_id: Node that left
            reason: Reason for leaving
            
        Returns:
            Updated status
        """
        # Update cluster manager
        self._cluster_manager.node_left(node_id, reason)
        
        # Update bootstrap
        await self._bootstrap.handle_node_leave(node_id)
        
        # Update degradation
        await self._update_degradation_level()
        
        return self.get_status()
    
    async def node_failed(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node failure.
        
        Args:
            node_id: Failed node
            
        Returns:
            Updated status
        """
        # Update cluster manager
        self._cluster_manager.node_failed(node_id)
        
        # Update degradation
        await self._update_degradation_level()
        
        return self.get_status()
    
    async def node_recovered(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node recovery.
        
        Args:
            node_id: Recovered node
            
        Returns:
            Updated status
        """
        # Update cluster manager
        self._cluster_manager.node_recovered(node_id)
        
        # Update degradation
        await self._update_degradation_level()
        
        return self.get_status()
    
    async def _update_degradation_level(self):
        """Update degradation level based on current state."""
        config = self._cluster_config
        old_level = self._degradation_level
        
        # Calculate new degradation level
        if config.operation_mode == OperationMode.READONLY:
            self._degradation_level = DegradationLevel.CRITICAL
            self._capabilities = SystemCapabilities(
                can_write=False,
                can_read=True,
                can_replicate=False,
                can_rebalance=False,
                strong_consistency_available=False,
                fault_tolerance_level=0
            )
        
        elif config.operation_mode == OperationMode.SINGLE_NODE:
            self._degradation_level = DegradationLevel.SIGNIFICANT
            self._capabilities = SystemCapabilities(
                can_write=True,
                can_read=True,
                can_replicate=False,
                can_rebalance=False,
                strong_consistency_available=False,  # Can't have consensus with 1 node
                fault_tolerance_level=0
            )
        
        elif config.current_nodes < config.target_nodes:
            if config.effective_replication_factor > 0:
                self._degradation_level = DegradationLevel.MODERATE
                self._capabilities = SystemCapabilities(
                    can_write=True,
                    can_read=True,
                    can_replicate=True,
                    can_rebalance=True,
                    strong_consistency_available=config.current_nodes >= 3,
                    fault_tolerance_level=config.get_fault_tolerance()
                )
            else:
                self._degradation_level = DegradationLevel.SIGNIFICANT
                self._capabilities = SystemCapabilities(
                    can_write=True,
                    can_read=True,
                    can_replicate=False,
                    can_rebalance=False,
                    strong_consistency_available=False,
                    fault_tolerance_level=0
                )
        
        else:
            # Full cluster available
            if config.effective_replication_factor >= config.target_replication_factor:
                self._degradation_level = DegradationLevel.NONE
            else:
                self._degradation_level = DegradationLevel.MINIMAL
            
            self._capabilities = SystemCapabilities(
                can_write=True,
                can_read=True,
                can_replicate=True,
                can_rebalance=True,
                strong_consistency_available=True,
                fault_tolerance_level=config.get_fault_tolerance()
            )
        
        # Notify if changed
        if old_level != self._degradation_level:
            logger.info(
                f"Degradation level changed: {old_level.name} -> {self._degradation_level.name}"
            )
            
            for callback in self._on_degradation_change:
                try:
                    await callback(self._degradation_level, self._capabilities)
                except Exception as e:
                    logger.error(f"Degradation callback error: {e}")
    
    async def _on_become_leader(self):
        """Callback when becoming leader."""
        logger.info(f"Node {self.node_id} became leader")
        await self._update_degradation_level()
    
    async def _on_join_cluster(self, leader_id: str):
        """Callback when joining cluster."""
        logger.info(f"Node {self.node_id} joined cluster with leader {leader_id}")
        await self._update_degradation_level()
    
    async def _on_cluster_formed(self, nodes: List[str]):
        """Callback when cluster formed."""
        logger.info(f"Cluster formed with {len(nodes)} nodes")
        await self._update_degradation_level()
    
    async def _monitor_loop(self):
        """Monitor and update degradation status."""
        while self._is_running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                # Periodic degradation update
                await self._update_degradation_level()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Degradation monitor error: {e}")
    
    def check_operation_allowed(self, operation: str) -> Dict[str, Any]:
        """
        Check if an operation is allowed in current degradation state.
        
        Args:
            operation: Operation type (write, read, replicate, etc.)
            
        Returns:
            Result with allowed status and reason
        """
        allowed = True
        reason = "Operation allowed"
        
        if operation == "write":
            allowed = self._capabilities.can_write
            if not allowed:
                reason = "Writes disabled in current partition state"
        
        elif operation == "read":
            allowed = self._capabilities.can_read
            if not allowed:
                reason = "Reads disabled"
        
        elif operation == "replicate":
            allowed = self._capabilities.can_replicate
            if not allowed:
                reason = "Replication unavailable (insufficient nodes)"
        
        elif operation == "rebalance":
            allowed = self._capabilities.can_rebalance
            if not allowed:
                reason = "Rebalancing unavailable (insufficient nodes)"
        
        elif operation == "strong_read":
            allowed = self._capabilities.strong_consistency_available
            if not allowed:
                reason = "Strong consistency unavailable (need quorum)"
        
        return {
            "allowed": allowed,
            "reason": reason,
            "degradation_level": self._degradation_level.name,
            "operation": operation
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status."""
        return {
            "node_id": self.node_id,
            "degradation_level": self._degradation_level.name,
            "degradation_value": self._degradation_level.value,
            "capabilities": self._capabilities.to_dict(),
            "cluster_config": self._cluster_config.to_dict(),
            "bootstrap_phase": self._bootstrap.phase.value,
            "is_leader": self._bootstrap.is_leader,
            "cluster_size": self._bootstrap.cluster_size,
            "summary": self._get_status_summary()
        }
    
    def _get_status_summary(self) -> str:
        """Get human-readable status summary."""
        summaries = {
            DegradationLevel.NONE: "System fully operational",
            DegradationLevel.MINIMAL: "System operational with slightly reduced redundancy",
            DegradationLevel.MODERATE: "System operational with reduced replication",
            DegradationLevel.SIGNIFICANT: "System running in single-node or limited mode",
            DegradationLevel.CRITICAL: "System in read-only or critical state"
        }
        return summaries.get(self._degradation_level, "Unknown state")

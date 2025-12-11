# -*- coding: utf-8 -*-
"""
Single Node Bootstrap Manager

Enables the system to start with a single node and grow incrementally.
Handles the transition from single-node to multi-node operation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class BootstrapPhase(Enum):
    """Bootstrap phases."""
    INITIALIZING = "initializing"
    SINGLE_NODE = "single_node"
    WAITING_FOR_PEERS = "waiting_for_peers"
    CLUSTER_FORMING = "cluster_forming"
    OPERATIONAL = "operational"


@dataclass
class BootstrapConfig:
    """Configuration for bootstrap process."""
    node_id: str
    node_address: str
    
    # Seed nodes to try connecting to
    seed_nodes: List[str] = field(default_factory=list)
    
    # Timing
    peer_discovery_interval_sec: float = 10.0
    startup_grace_period_sec: float = 30.0
    max_discovery_attempts: int = 3
    
    # Single node operation
    allow_single_node: bool = True
    auto_promote_to_leader: bool = True


class SingleNodeBootstrap:
    """
    Manages single-node bootstrap and cluster growth.
    
    Behavior:
    1. On startup, try to find existing cluster via seed nodes
    2. If no cluster found and allow_single_node=True, become standalone leader
    3. Accept joining nodes and transition to cluster mode
    4. Handle the entire lifecycle from single node to full cluster
    """
    
    def __init__(
        self,
        config: BootstrapConfig,
        on_become_leader: Optional[Callable[[], Awaitable[None]]] = None,
        on_join_cluster: Optional[Callable[[str], Awaitable[None]]] = None,
        on_cluster_formed: Optional[Callable[[List[str]], Awaitable[None]]] = None
    ):
        """
        Initialize bootstrap manager.
        
        Args:
            config: Bootstrap configuration
            on_become_leader: Called when becoming standalone leader
            on_join_cluster: Called when joining existing cluster
            on_cluster_formed: Called when cluster reaches operational state
        """
        self.config = config
        self._on_become_leader = on_become_leader
        self._on_join_cluster = on_join_cluster
        self._on_cluster_formed = on_cluster_formed
        
        self._phase = BootstrapPhase.INITIALIZING
        self._is_leader = False
        self._leader_id: Optional[str] = None
        self._cluster_nodes: List[str] = [config.node_id]
        self._discovery_attempts = 0
        
        self._started_at: Optional[datetime] = None
        self._became_leader_at: Optional[datetime] = None
        self._joined_cluster_at: Optional[datetime] = None
        
        self._discovery_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    @property
    def phase(self) -> BootstrapPhase:
        """Current bootstrap phase."""
        return self._phase
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._is_leader
    
    @property
    def leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        return self._leader_id if self._leader_id else (
            self.config.node_id if self._is_leader else None
        )
    
    @property
    def cluster_size(self) -> int:
        """Current cluster size."""
        return len(self._cluster_nodes)
    
    async def start(self) -> Dict[str, Any]:
        """
        Start the bootstrap process.
        
        Returns:
            Bootstrap result including final phase and leader info
        """
        self._started_at = datetime.utcnow()
        self._is_running = True
        
        logger.info(f"Starting bootstrap for node {self.config.node_id}")
        
        # Phase 1: Try to discover existing cluster
        self._phase = BootstrapPhase.WAITING_FOR_PEERS
        
        cluster_found = await self._discover_cluster()
        
        if cluster_found:
            # Join existing cluster
            self._phase = BootstrapPhase.CLUSTER_FORMING
            return await self._join_existing_cluster()
        
        # No cluster found
        if self.config.allow_single_node:
            # Become standalone leader
            return await self._become_standalone_leader()
        else:
            # Keep trying to find cluster
            self._discovery_task = asyncio.create_task(self._discovery_loop())
            return {
                "phase": self._phase.value,
                "message": "Waiting for cluster peers",
                "node_id": self.config.node_id
            }
    
    async def stop(self) -> None:
        """Stop the bootstrap process."""
        self._is_running = False
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Bootstrap manager stopped")
    
    async def _discover_cluster(self) -> bool:
        """
        Try to discover an existing cluster.
        
        Returns:
            True if cluster found
        """
        if not self.config.seed_nodes:
            logger.info("No seed nodes configured, cannot discover existing cluster")
            return False
        
        logger.info(f"Attempting to discover cluster via {len(self.config.seed_nodes)} seed nodes")
        
        for seed in self.config.seed_nodes:
            try:
                # In real implementation, would send discovery request
                # For now, simulate with a placeholder
                result = await self._probe_seed_node(seed)
                
                if result and result.get("cluster_exists"):
                    self._leader_id = result.get("leader_id")
                    logger.info(f"Found existing cluster via {seed}, leader: {self._leader_id}")
                    return True
                    
            except Exception as e:
                logger.warning(f"Failed to probe seed {seed}: {e}")
        
        return False
    
    async def _probe_seed_node(self, seed_address: str) -> Optional[Dict[str, Any]]:
        """
        Probe a seed node for cluster information.
        
        In real implementation, this would send a gRPC/HTTP request.
        """
        # Placeholder - in real implementation would make network call
        await asyncio.sleep(0.1)
        
        # Return None to indicate no cluster found (for initial bootstrap)
        return None
    
    async def _become_standalone_leader(self) -> Dict[str, Any]:
        """
        Become a standalone leader (single-node cluster).
        
        Returns:
            Bootstrap result
        """
        self._is_leader = True
        self._leader_id = self.config.node_id
        self._became_leader_at = datetime.utcnow()
        self._phase = BootstrapPhase.SINGLE_NODE
        
        logger.info(f"Node {self.config.node_id} becoming standalone leader")
        
        if self._on_become_leader:
            await self._on_become_leader()
        
        return {
            "phase": self._phase.value,
            "is_leader": True,
            "leader_id": self._leader_id,
            "cluster_size": 1,
            "message": "Operating as single-node cluster",
            "node_id": self.config.node_id
        }
    
    async def _join_existing_cluster(self) -> Dict[str, Any]:
        """
        Join an existing cluster.
        
        Returns:
            Bootstrap result
        """
        self._is_leader = False
        self._joined_cluster_at = datetime.utcnow()
        
        logger.info(f"Node {self.config.node_id} joining cluster with leader {self._leader_id}")
        
        if self._on_join_cluster:
            await self._on_join_cluster(self._leader_id)
        
        self._phase = BootstrapPhase.OPERATIONAL
        
        return {
            "phase": self._phase.value,
            "is_leader": False,
            "leader_id": self._leader_id,
            "cluster_size": len(self._cluster_nodes),
            "message": "Joined existing cluster",
            "node_id": self.config.node_id
        }
    
    async def _discovery_loop(self) -> None:
        """Background loop for cluster discovery."""
        while self._is_running and self._discovery_attempts < self.config.max_discovery_attempts:
            try:
                await asyncio.sleep(self.config.peer_discovery_interval_sec)
                
                self._discovery_attempts += 1
                cluster_found = await self._discover_cluster()
                
                if cluster_found:
                    await self._join_existing_cluster()
                    return
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
        
        # Max attempts reached, become standalone if allowed
        if self.config.allow_single_node and not self._is_leader:
            await self._become_standalone_leader()
    
    async def handle_node_join(self, node_id: str, node_address: str) -> Dict[str, Any]:
        """
        Handle a new node joining the cluster.
        
        Called when this node (as leader) receives a join request.
        
        Args:
            node_id: Joining node's ID
            node_address: Joining node's address
            
        Returns:
            Join result
        """
        if not self._is_leader:
            return {
                "success": False,
                "error": "Not the leader",
                "leader_id": self._leader_id
            }
        
        if node_id in self._cluster_nodes:
            return {
                "success": True,
                "message": "Node already in cluster",
                "cluster_size": len(self._cluster_nodes)
            }
        
        # Add node to cluster
        self._cluster_nodes.append(node_id)
        
        # Transition from single-node to multi-node
        if self._phase == BootstrapPhase.SINGLE_NODE:
            self._phase = BootstrapPhase.CLUSTER_FORMING
            logger.info(f"Transitioning from single-node to cluster mode (size: {len(self._cluster_nodes)})")
        
        # Check if we've reached operational state
        if len(self._cluster_nodes) >= 2:
            self._phase = BootstrapPhase.OPERATIONAL
            
            if self._on_cluster_formed:
                await self._on_cluster_formed(self._cluster_nodes)
        
        logger.info(f"Node {node_id} joined cluster. Size: {len(self._cluster_nodes)}")
        
        return {
            "success": True,
            "leader_id": self._leader_id,
            "cluster_size": len(self._cluster_nodes),
            "cluster_nodes": self._cluster_nodes.copy(),
            "phase": self._phase.value
        }
    
    async def handle_node_leave(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node leaving the cluster.
        
        Args:
            node_id: Leaving node's ID
            
        Returns:
            Leave result
        """
        if node_id not in self._cluster_nodes:
            return {"success": True, "message": "Node not in cluster"}
        
        self._cluster_nodes.remove(node_id)
        
        # Check if we're back to single-node
        if len(self._cluster_nodes) == 1:
            self._phase = BootstrapPhase.SINGLE_NODE
            logger.info("Reverted to single-node operation")
        
        # If leader left, need new election (handled by Raft)
        if node_id == self._leader_id:
            self._leader_id = None
            self._is_leader = False  # Will be determined by Raft election
        
        logger.info(f"Node {node_id} left cluster. Size: {len(self._cluster_nodes)}")
        
        return {
            "success": True,
            "cluster_size": len(self._cluster_nodes),
            "phase": self._phase.value
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get bootstrap status."""
        return {
            "node_id": self.config.node_id,
            "phase": self._phase.value,
            "is_leader": self._is_leader,
            "leader_id": self._leader_id,
            "cluster_size": len(self._cluster_nodes),
            "cluster_nodes": self._cluster_nodes.copy(),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "became_leader_at": self._became_leader_at.isoformat() if self._became_leader_at else None,
            "joined_cluster_at": self._joined_cluster_at.isoformat() if self._joined_cluster_at else None,
            "discovery_attempts": self._discovery_attempts
        }

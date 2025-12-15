# -*- coding: utf-8 -*-
"""
Adaptive Cluster Configuration

Dynamically adjusts cluster parameters based on available nodes.
Supports:
- Starting with a single node
- Growing incrementally
- Operating with fewer nodes than expected
- Graceful degradation during network partitions
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ConsistencyLevel(Enum):
    """Consistency levels based on available nodes."""
    STRONG = "strong"       # All nodes must agree (requires majority)
    EVENTUAL = "eventual"   # Best effort, async replication
    LOCAL = "local"         # Single node, no replication
    QUORUM = "quorum"       # Majority of available nodes


class OperationMode(Enum):
    """Cluster operation mode based on health."""
    NORMAL = "normal"           # Full functionality
    DEGRADED = "degraded"       # Reduced replication/quorum
    SINGLE_NODE = "single_node" # Operating alone
    PARTITIONED = "partitioned" # Network partition detected
    READONLY = "readonly"       # Read-only mode (split-brain protection)


@dataclass
class AdaptiveClusterConfig:
    """
    Adaptive configuration that adjusts based on cluster state.
    
    Key principle: System should ALWAYS operate, even with 1 node.
    k-fault tolerance only applies when k+1 nodes are available.
    """
    
    # Target configuration (ideal state)
    target_nodes: int = 3
    target_replication_factor: int = 2
    target_quorum_size: int = 2
    
    # Current effective configuration
    current_nodes: int = 1
    effective_replication_factor: int = 1
    effective_quorum_size: int = 1
    
    # Operation mode
    operation_mode: OperationMode = OperationMode.SINGLE_NODE
    consistency_level: ConsistencyLevel = ConsistencyLevel.LOCAL
    
    # Thresholds
    min_nodes_for_replication: int = 2
    min_nodes_for_quorum: int = 3
    
    # State
    is_partitioned: bool = False
    partition_id: Optional[str] = None
    last_update: datetime = field(default_factory=datetime.utcnow)
    
    def update_for_cluster_size(self, available_nodes: int) -> Dict[str, Any]:
        """
        Update configuration based on available nodes.
        
        Args:
            available_nodes: Number of currently available nodes
            
        Returns:
            Dictionary of changes made
        """
        old_config = {
            "nodes": self.current_nodes,
            "replication_factor": self.effective_replication_factor,
            "quorum_size": self.effective_quorum_size,
            "mode": self.operation_mode.value,
            "consistency": self.consistency_level.value,
        }
        
        self.current_nodes = available_nodes
        self.last_update = datetime.utcnow()
        
        # Calculate effective replication factor
        # Can't replicate more than available nodes
        if available_nodes >= self.target_replication_factor + 1:
            # We have enough nodes for full replication
            self.effective_replication_factor = self.target_replication_factor
        elif available_nodes >= 2:
            # At least 2 nodes - replicate to one other node
            self.effective_replication_factor = 1
        else:
            # Single node - no replication possible
            self.effective_replication_factor = 0
        
        # Calculate effective quorum size
        # Quorum = floor(n/2) + 1 where n = available nodes
        if available_nodes >= self.min_nodes_for_quorum:
            self.effective_quorum_size = (available_nodes // 2) + 1
        elif available_nodes >= 2:
            # With 2 nodes, need both for strong consistency
            # Or operate with eventual consistency
            self.effective_quorum_size = 2
        else:
            # Single node - quorum of 1
            self.effective_quorum_size = 1
        
        # Determine operation mode
        if available_nodes == 1:
            self.operation_mode = OperationMode.SINGLE_NODE
            self.consistency_level = ConsistencyLevel.LOCAL
        elif available_nodes < self.target_nodes:
            self.operation_mode = OperationMode.DEGRADED
            if available_nodes >= self.min_nodes_for_quorum:
                self.consistency_level = ConsistencyLevel.QUORUM
            else:
                self.consistency_level = ConsistencyLevel.EVENTUAL
        else:
            self.operation_mode = OperationMode.NORMAL
            self.consistency_level = ConsistencyLevel.STRONG
        
        new_config = {
            "nodes": self.current_nodes,
            "replication_factor": self.effective_replication_factor,
            "quorum_size": self.effective_quorum_size,
            "mode": self.operation_mode.value,
            "consistency": self.consistency_level.value,
        }
        
        changes = {
            k: {"old": old_config[k], "new": new_config[k]}
            for k in old_config
            if old_config[k] != new_config[k]
        }
        
        if changes:
            logger.info(f"Cluster config updated: {changes}")
        
        return changes
    
    def handle_partition(self, nodes_in_partition: List[str], total_known_nodes: int):
        """
        Handle network partition scenario.
        
        In a partition, continue operating with available nodes but
        potentially enter read-only mode to prevent split-brain.
        
        Args:
            nodes_in_partition: Nodes we can still communicate with
            total_known_nodes: Total nodes known before partition
        """
        partition_size = len(nodes_in_partition)
        
        self.is_partitioned = True
        self.partition_id = f"partition_{datetime.utcnow().timestamp()}"
        
        # If we have majority, we can continue with writes
        if partition_size > total_known_nodes // 2:
            logger.info(f"We are in majority partition ({partition_size}/{total_known_nodes})")
            self.update_for_cluster_size(partition_size)
        else:
            # Minority partition - go read-only to prevent split-brain
            logger.warning(f"We are in minority partition ({partition_size}/{total_known_nodes}), going read-only")
            self.operation_mode = OperationMode.READONLY
            self.consistency_level = ConsistencyLevel.LOCAL
            self.effective_quorum_size = partition_size
    
    def heal_partition(self, all_nodes: List[str]):
        """
        Handle partition healing.
        
        Args:
            all_nodes: All nodes now reachable
        """
        self.is_partitioned = False
        self.partition_id = None
        self.update_for_cluster_size(len(all_nodes))
        logger.info(f"Partition healed, cluster restored with {len(all_nodes)} nodes")
    
    def can_write(self) -> bool:
        """Check if writes are allowed in current mode."""
        return self.operation_mode != OperationMode.READONLY
    
    def get_min_replicas_for_ack(self) -> int:
        """
        Get minimum replicas needed to acknowledge a write.
        
        For durability without blocking, we acknowledge writes when
        at least one replica confirms (if replication is enabled).
        """
        if self.effective_replication_factor == 0:
            return 0  # Single node, no replicas needed
        return 1  # At least one replica should confirm
    
    def get_quorum_for_read(self) -> int:
        """
        Get nodes needed for quorum read.
        
        For strong consistency, read from quorum.
        For eventual consistency, read from any available node.
        """
        if self.consistency_level == ConsistencyLevel.LOCAL:
            return 1
        elif self.consistency_level == ConsistencyLevel.EVENTUAL:
            return 1
        elif self.consistency_level == ConsistencyLevel.QUORUM:
            return self.effective_quorum_size
        else:  # STRONG
            return self.effective_quorum_size
    
    def get_fault_tolerance(self) -> int:
        """
        Get current fault tolerance level (k).
        
        With n nodes and replication factor r, can tolerate r-1 failures
        while maintaining at least one copy.
        """
        return max(0, self.effective_replication_factor)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration to dictionary."""
        return {
            "target": {
                "nodes": self.target_nodes,
                "replication_factor": self.target_replication_factor,
                "quorum_size": self.target_quorum_size,
            },
            "effective": {
                "nodes": self.current_nodes,
                "replication_factor": self.effective_replication_factor,
                "quorum_size": self.effective_quorum_size,
            },
            "operation_mode": self.operation_mode.value,
            "consistency_level": self.consistency_level.value,
            "fault_tolerance": self.get_fault_tolerance(),
            "can_write": self.can_write(),
            "is_partitioned": self.is_partitioned,
            "last_update": self.last_update.isoformat(),
        }


class AdaptiveClusterManager:
    """
    Manages adaptive cluster behavior.
    
    Responds to cluster changes and adjusts configuration automatically.
    """
    
    def __init__(
        self,
        config: Optional[AdaptiveClusterConfig] = None,
        node_id: Optional[str] = None
    ):
        self.config = config or AdaptiveClusterConfig()
        self.node_id = node_id
        self._known_nodes: Dict[str, Dict[str, Any]] = {}
        self._healthy_nodes: List[str] = []
        
    def node_joined(self, node_id: str, node_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a new node joining the cluster.
        
        Args:
            node_id: New node's ID
            node_info: Node information
            
        Returns:
            Updated configuration changes
        """
        self._known_nodes[node_id] = {
            **node_info,
            "joined_at": datetime.utcnow().isoformat(),
            "status": "healthy"
        }
        self._healthy_nodes.append(node_id)
        
        # Update configuration
        changes = self.config.update_for_cluster_size(len(self._healthy_nodes))
        
        logger.info(f"Node {node_id} joined. Cluster now has {len(self._healthy_nodes)} nodes")
        
        return changes
    
    def node_left(self, node_id: str, reason: str = "unknown") -> Dict[str, Any]:
        """
        Handle a node leaving the cluster.
        
        Args:
            node_id: Node that left
            reason: Reason for leaving
            
        Returns:
            Updated configuration changes
        """
        if node_id in self._known_nodes:
            self._known_nodes[node_id]["status"] = "left"
            self._known_nodes[node_id]["left_reason"] = reason
            
        if node_id in self._healthy_nodes:
            self._healthy_nodes.remove(node_id)
        
        # Update configuration
        changes = self.config.update_for_cluster_size(len(self._healthy_nodes))
        
        logger.info(f"Node {node_id} left ({reason}). Cluster now has {len(self._healthy_nodes)} nodes")
        
        return changes
    
    def node_failed(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node failure.
        
        Args:
            node_id: Failed node
            
        Returns:
            Updated configuration changes
        """
        if node_id in self._known_nodes:
            self._known_nodes[node_id]["status"] = "failed"
            
        if node_id in self._healthy_nodes:
            self._healthy_nodes.remove(node_id)
        
        # Check if this could be a partition
        if len(self._healthy_nodes) < len(self._known_nodes) // 2:
            # Possibly in minority partition
            self.config.handle_partition(
                self._healthy_nodes, 
                len([n for n in self._known_nodes.values() if n.get("status") != "left"])
            )
        else:
            # Just node failure, update config
            self.config.update_for_cluster_size(len(self._healthy_nodes))
        
        return self.config.to_dict()
    
    def node_recovered(self, node_id: str) -> Dict[str, Any]:
        """
        Handle a node recovery.
        
        Args:
            node_id: Recovered node
            
        Returns:
            Updated configuration changes
        """
        if node_id in self._known_nodes:
            self._known_nodes[node_id]["status"] = "healthy"
            
        if node_id not in self._healthy_nodes:
            self._healthy_nodes.append(node_id)
        
        # Check if partition healed
        if self.config.is_partitioned:
            active_nodes = [n for n, info in self._known_nodes.items() 
                          if info.get("status") == "healthy"]
            total_known = len([n for n, info in self._known_nodes.items() 
                             if info.get("status") != "left"])
            
            if len(active_nodes) > total_known // 2:
                self.config.heal_partition(active_nodes)
        else:
            self.config.update_for_cluster_size(len(self._healthy_nodes))
        
        return self.config.to_dict()
    
    def get_replication_targets(
        self, 
        primary_node: str,
        exclude_nodes: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get target nodes for replication based on current config.
        
        Args:
            primary_node: Node holding primary copy
            exclude_nodes: Nodes to exclude from selection
            
        Returns:
            List of nodes to replicate to
        """
        exclude = set(exclude_nodes or [])
        exclude.add(primary_node)
        
        available = [n for n in self._healthy_nodes if n not in exclude]
        
        # Return up to effective_replication_factor nodes
        return available[:self.config.effective_replication_factor]
    
    def should_replicate(self) -> bool:
        """Check if replication should be performed."""
        return self.config.effective_replication_factor > 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get adaptive cluster status."""
        return {
            "node_id": self.node_id,
            "config": self.config.to_dict(),
            "known_nodes": len(self._known_nodes),
            "healthy_nodes": len(self._healthy_nodes),
            "nodes": {
                node_id: info.get("status", "unknown")
                for node_id, info in self._known_nodes.items()
            }
        }

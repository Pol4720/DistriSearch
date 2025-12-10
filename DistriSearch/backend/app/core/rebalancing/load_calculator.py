# -*- coding: utf-8 -*-
"""
Load Calculator - Calculates load metrics and rebalance decisions.

Analyzes cluster load distribution and determines when and how
to rebalance documents across nodes.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LoadLevel(Enum):
    """Load level categories."""
    CRITICAL = "critical"  # > 90%
    HIGH = "high"          # > 75%
    NORMAL = "normal"      # 40-75%
    LOW = "low"            # < 40%
    EMPTY = "empty"        # 0%


@dataclass
class LoadMetrics:
    """Load metrics for a single node."""
    node_id: str
    document_count: int
    capacity: int
    storage_used_bytes: int = 0
    storage_capacity_bytes: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    query_rate: float = 0.0  # queries per second
    avg_latency_ms: float = 0.0
    is_healthy: bool = True
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def load_factor(self) -> float:
        """Document load factor (0-1)."""
        return self.document_count / self.capacity if self.capacity > 0 else 1.0
    
    @property
    def storage_factor(self) -> float:
        """Storage load factor (0-1)."""
        if self.storage_capacity_bytes <= 0:
            return 0.0
        return self.storage_used_bytes / self.storage_capacity_bytes
    
    @property
    def combined_load(self) -> float:
        """Combined load metric (weighted average)."""
        # Weights for different metrics
        doc_weight = 0.4
        storage_weight = 0.2
        cpu_weight = 0.2
        memory_weight = 0.2
        
        return (
            doc_weight * self.load_factor +
            storage_weight * self.storage_factor +
            cpu_weight * self.cpu_usage +
            memory_weight * self.memory_usage
        )
    
    @property
    def load_level(self) -> LoadLevel:
        """Categorize load level."""
        load = self.load_factor
        
        if load <= 0:
            return LoadLevel.EMPTY
        elif load < 0.4:
            return LoadLevel.LOW
        elif load < 0.75:
            return LoadLevel.NORMAL
        elif load < 0.9:
            return LoadLevel.HIGH
        else:
            return LoadLevel.CRITICAL
    
    @property
    def available_capacity(self) -> int:
        """Documents that can still be added."""
        return max(0, self.capacity - self.document_count)


@dataclass
class RebalanceDecision:
    """Decision about rebalancing."""
    should_rebalance: bool
    reason: str
    source_node: Optional[str] = None
    target_node: Optional[str] = None
    documents_to_move: int = 0
    priority: int = 0  # Higher = more urgent
    estimated_duration_sec: float = 0.0


@dataclass
class ClusterLoadSummary:
    """Summary of cluster-wide load."""
    total_documents: int
    total_capacity: int
    node_count: int
    healthy_nodes: int
    avg_load_factor: float
    load_variance: float
    load_std_dev: float
    min_load_factor: float
    max_load_factor: float
    imbalance_ratio: float
    overloaded_nodes: List[str]
    underloaded_nodes: List[str]
    critical_nodes: List[str]


class LoadCalculator:
    """
    Calculates load metrics and makes rebalancing decisions.
    
    Monitors cluster load distribution and determines optimal
    document migrations to maintain balance.
    """
    
    def __init__(
        self,
        imbalance_threshold: float = 0.2,
        critical_threshold: float = 0.9,
        min_transfer_size: int = 10,
        target_load_factor: float = 0.6
    ):
        """
        Initialize load calculator.
        
        Args:
            imbalance_threshold: Max load variance before rebalancing
            critical_threshold: Load factor considered critical
            min_transfer_size: Minimum docs to transfer
            target_load_factor: Target load for balanced state
        """
        self.imbalance_threshold = imbalance_threshold
        self.critical_threshold = critical_threshold
        self.min_transfer_size = min_transfer_size
        self.target_load_factor = target_load_factor
        
        self._metrics: Dict[str, LoadMetrics] = {}
        self._history: List[ClusterLoadSummary] = []
    
    def update_node_metrics(
        self,
        node_id: str,
        metrics: LoadMetrics
    ) -> None:
        """
        Update metrics for a node.
        
        Args:
            node_id: Node identifier
            metrics: Updated metrics
        """
        self._metrics[node_id] = metrics
    
    def update_node_from_dict(
        self,
        node_id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Update node metrics from dictionary.
        
        Args:
            node_id: Node identifier
            data: Metrics data dictionary
        """
        existing = self._metrics.get(node_id)
        
        metrics = LoadMetrics(
            node_id=node_id,
            document_count=data.get("document_count", existing.document_count if existing else 0),
            capacity=data.get("capacity", existing.capacity if existing else 10000),
            storage_used_bytes=data.get("storage_used_bytes", 0),
            storage_capacity_bytes=data.get("storage_capacity_bytes", 0),
            cpu_usage=data.get("cpu_usage", 0.0),
            memory_usage=data.get("memory_usage", 0.0),
            query_rate=data.get("query_rate", 0.0),
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            is_healthy=data.get("is_healthy", True),
        )
        
        self._metrics[node_id] = metrics
    
    def remove_node(self, node_id: str) -> None:
        """Remove node from tracking."""
        self._metrics.pop(node_id, None)
    
    def get_node_metrics(self, node_id: str) -> Optional[LoadMetrics]:
        """Get metrics for a node."""
        return self._metrics.get(node_id)
    
    def get_all_metrics(self) -> Dict[str, LoadMetrics]:
        """Get all node metrics."""
        return dict(self._metrics)
    
    def calculate_cluster_summary(self) -> ClusterLoadSummary:
        """
        Calculate cluster-wide load summary.
        
        Returns:
            Cluster load summary
        """
        if not self._metrics:
            return ClusterLoadSummary(
                total_documents=0,
                total_capacity=0,
                node_count=0,
                healthy_nodes=0,
                avg_load_factor=0.0,
                load_variance=0.0,
                load_std_dev=0.0,
                min_load_factor=0.0,
                max_load_factor=0.0,
                imbalance_ratio=0.0,
                overloaded_nodes=[],
                underloaded_nodes=[],
                critical_nodes=[]
            )
        
        metrics_list = list(self._metrics.values())
        healthy = [m for m in metrics_list if m.is_healthy]
        
        load_factors = [m.load_factor for m in healthy] if healthy else [0.0]
        
        total_docs = sum(m.document_count for m in metrics_list)
        total_cap = sum(m.capacity for m in metrics_list)
        
        avg_load = np.mean(load_factors)
        load_var = np.var(load_factors)
        load_std = np.std(load_factors)
        min_load = min(load_factors)
        max_load = max(load_factors)
        
        # Imbalance ratio: how much max differs from min relative to avg
        imbalance = (max_load - min_load) / avg_load if avg_load > 0 else 0.0
        
        # Categorize nodes
        overloaded = [m.node_id for m in healthy if m.load_factor > 0.75]
        underloaded = [m.node_id for m in healthy if m.load_factor < 0.4]
        critical = [m.node_id for m in healthy if m.load_factor > self.critical_threshold]
        
        summary = ClusterLoadSummary(
            total_documents=total_docs,
            total_capacity=total_cap,
            node_count=len(metrics_list),
            healthy_nodes=len(healthy),
            avg_load_factor=float(avg_load),
            load_variance=float(load_var),
            load_std_dev=float(load_std),
            min_load_factor=float(min_load),
            max_load_factor=float(max_load),
            imbalance_ratio=float(imbalance),
            overloaded_nodes=overloaded,
            underloaded_nodes=underloaded,
            critical_nodes=critical
        )
        
        # Keep history
        self._history.append(summary)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        return summary
    
    def needs_rebalancing(self) -> Tuple[bool, str]:
        """
        Determine if cluster needs rebalancing.
        
        Returns:
            Tuple of (needs_rebalance, reason)
        """
        summary = self.calculate_cluster_summary()
        
        if summary.node_count < 2:
            return False, "Insufficient nodes for rebalancing"
        
        if summary.healthy_nodes < 2:
            return False, "Insufficient healthy nodes"
        
        if summary.critical_nodes:
            return True, f"Critical load on nodes: {summary.critical_nodes}"
        
        if summary.load_std_dev > self.imbalance_threshold:
            return True, f"Load imbalance detected (std_dev={summary.load_std_dev:.3f})"
        
        if summary.imbalance_ratio > 0.5:
            return True, f"High imbalance ratio: {summary.imbalance_ratio:.2f}"
        
        return False, "Cluster is balanced"
    
    def calculate_optimal_distribution(self) -> Dict[str, int]:
        """
        Calculate optimal document distribution.
        
        Returns:
            Mapping of node_id -> target_document_count
        """
        healthy = {
            node_id: m for node_id, m in self._metrics.items()
            if m.is_healthy
        }
        
        if not healthy:
            return {}
        
        total_docs = sum(m.document_count for m in healthy.values())
        total_cap = sum(m.capacity for m in healthy.values())
        
        # Distribute proportionally to capacity
        distribution = {}
        for node_id, metrics in healthy.items():
            capacity_ratio = metrics.capacity / total_cap if total_cap > 0 else 0
            target = int(total_docs * capacity_ratio)
            distribution[node_id] = min(target, metrics.capacity)
        
        return distribution
    
    def generate_rebalance_plan(self) -> List[RebalanceDecision]:
        """
        Generate a plan for rebalancing the cluster.
        
        Returns:
            List of rebalance decisions/migrations
        """
        decisions = []
        optimal = self.calculate_optimal_distribution()
        
        if not optimal:
            return decisions
        
        # Calculate deltas
        deltas = {}
        for node_id, target in optimal.items():
            metrics = self._metrics[node_id]
            delta = metrics.document_count - target
            deltas[node_id] = delta
        
        # Match sources (positive delta) with targets (negative delta)
        sources = [(n, d) for n, d in deltas.items() if d > self.min_transfer_size]
        targets = [(n, -d) for n, d in deltas.items() if d < -self.min_transfer_size]
        
        sources.sort(key=lambda x: x[1], reverse=True)  # Most overloaded first
        targets.sort(key=lambda x: x[1], reverse=True)  # Most underloaded first
        
        for source_id, excess in sources:
            remaining = excess
            
            for target_id, capacity in targets:
                if remaining <= 0 or capacity <= 0:
                    continue
                
                to_move = min(remaining, capacity)
                if to_move >= self.min_transfer_size:
                    # Calculate priority based on source load
                    source_metrics = self._metrics[source_id]
                    priority = 3 if source_metrics.load_level == LoadLevel.CRITICAL else \
                              2 if source_metrics.load_level == LoadLevel.HIGH else 1
                    
                    # Estimate duration (50 docs/batch, 1s between batches)
                    batches = (to_move + 49) // 50
                    duration = batches * 1.5  # 1s sleep + ~0.5s transfer
                    
                    decisions.append(RebalanceDecision(
                        should_rebalance=True,
                        reason=f"Load balancing: {source_id} -> {target_id}",
                        source_node=source_id,
                        target_node=target_id,
                        documents_to_move=to_move,
                        priority=priority,
                        estimated_duration_sec=duration
                    ))
                    
                    remaining -= to_move
                    # Update target's remaining capacity
                    targets = [(n, c - to_move if n == target_id else c) 
                              for n, c in targets]
        
        # Sort by priority
        decisions.sort(key=lambda d: d.priority, reverse=True)
        
        return decisions
    
    def get_migration_candidates(
        self,
        source_node: str,
        count: int
    ) -> Dict[str, Any]:
        """
        Get information for selecting migration candidates.
        
        Args:
            source_node: Node to migrate from
            count: Number of documents to migrate
            
        Returns:
            Migration criteria for document selection
        """
        return {
            "source_node": source_node,
            "count": count,
            "criteria": {
                # Prefer documents that:
                # 1. Have low access frequency
                # 2. Are semantically distant from node's centroid
                # 3. Have recently completed replication
                "prefer_low_access": True,
                "prefer_semantic_outliers": True,
                "require_replicated": True
            }
        }
    
    def estimate_rebalance_impact(
        self,
        decisions: List[RebalanceDecision]
    ) -> Dict[str, Any]:
        """
        Estimate impact of rebalance plan.
        
        Args:
            decisions: Proposed rebalance decisions
            
        Returns:
            Impact assessment
        """
        if not decisions:
            return {"no_changes": True}
        
        total_docs = sum(d.documents_to_move for d in decisions)
        total_batches = sum((d.documents_to_move + 49) // 50 for d in decisions)
        total_duration = sum(d.estimated_duration_sec for d in decisions)
        
        # Simulate new load distribution
        new_loads = {n: m.document_count for n, m in self._metrics.items()}
        
        for decision in decisions:
            if decision.source_node in new_loads:
                new_loads[decision.source_node] -= decision.documents_to_move
            if decision.target_node in new_loads:
                new_loads[decision.target_node] += decision.documents_to_move
        
        new_factors = {
            n: count / self._metrics[n].capacity 
            for n, count in new_loads.items()
            if n in self._metrics and self._metrics[n].capacity > 0
        }
        
        new_std = np.std(list(new_factors.values())) if new_factors else 0.0
        current_std = np.std([m.load_factor for m in self._metrics.values()])
        
        return {
            "total_documents_moved": total_docs,
            "total_batches": total_batches,
            "estimated_duration_sec": total_duration,
            "current_load_std": float(current_std),
            "projected_load_std": float(new_std),
            "improvement_ratio": float((current_std - new_std) / current_std) if current_std > 0 else 0,
            "migrations": len(decisions),
            "affected_nodes": len(set(
                [d.source_node for d in decisions] + [d.target_node for d in decisions]
            ))
        }

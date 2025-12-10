# -*- coding: utf-8 -*-
"""
Active Rebalancer - Orchestrates cluster rebalancing operations.

Implements proactive rebalancing with:
- Load monitoring
- Migration planning
- Batch execution with rate limiting
- Progress tracking
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .load_calculator import LoadCalculator, LoadMetrics, RebalanceDecision, ClusterLoadSummary
from .migration_handler import MigrationHandler, MigrationTask, MigrationResult, MigrationConfig

logger = logging.getLogger(__name__)


class RebalanceStatus(Enum):
    """Status of rebalance operation."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class RebalanceConfig:
    """Configuration for rebalancing."""
    # Thresholds
    imbalance_threshold: float = 0.2
    critical_threshold: float = 0.9
    min_documents_to_move: int = 10
    
    # Timing
    check_interval_sec: float = 60.0
    cooldown_after_rebalance_sec: float = 300.0  # 5 min cooldown
    
    # Migration settings (per architecture spec)
    batch_size: int = 50
    batch_delay_sec: float = 1.0
    max_concurrent_migrations: int = 2
    
    # Limits
    max_documents_per_rebalance: int = 1000
    max_duration_sec: float = 3600.0  # 1 hour max


@dataclass
class RebalanceOperation:
    """Represents a rebalance operation."""
    operation_id: str
    status: RebalanceStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    decisions: List[RebalanceDecision] = field(default_factory=list)
    migration_tasks: List[str] = field(default_factory=list)
    documents_moved: int = 0
    documents_failed: int = 0
    error_message: Optional[str] = None
    
    @property
    def duration_sec(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.utcnow() - self.started_at).total_seconds()


class ActiveRebalancer:
    """
    Actively monitors and rebalances cluster load.
    
    Features:
    - Continuous load monitoring
    - Automatic rebalance triggering
    - Coordinated migrations with rate limiting
    - Operation history tracking
    """
    
    def __init__(
        self,
        config: Optional[RebalanceConfig] = None,
        document_selector: Optional[Callable[[str, int], Awaitable[List[str]]]] = None,
        transfer_func: Optional[Callable[[str, str, List[str]], Awaitable[Dict[str, Any]]]] = None
    ):
        """
        Initialize active rebalancer.
        
        Args:
            config: Rebalancing configuration
            document_selector: Function to select documents for migration
                              Signature: (node_id, count) -> list of doc_ids
            transfer_func: Function to transfer documents between nodes
        """
        self.config = config or RebalanceConfig()
        self._document_selector = document_selector
        
        # Initialize components
        self.load_calculator = LoadCalculator(
            imbalance_threshold=self.config.imbalance_threshold,
            critical_threshold=self.config.critical_threshold,
            min_transfer_size=self.config.min_documents_to_move
        )
        
        migration_config = MigrationConfig(
            batch_size=self.config.batch_size,
            batch_delay_sec=self.config.batch_delay_sec
        )
        self.migration_handler = MigrationHandler(
            config=migration_config,
            transfer_func=transfer_func
        )
        
        # State
        self._status = RebalanceStatus.IDLE
        self._current_operation: Optional[RebalanceOperation] = None
        self._operation_history: List[RebalanceOperation] = []
        self._last_rebalance: Optional[datetime] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._operation_counter = 0
    
    @property
    def status(self) -> RebalanceStatus:
        return self._status
    
    @property
    def is_in_cooldown(self) -> bool:
        if not self._last_rebalance:
            return False
        cooldown_end = self._last_rebalance + timedelta(
            seconds=self.config.cooldown_after_rebalance_sec
        )
        return datetime.utcnow() < cooldown_end
    
    def update_node_metrics(
        self,
        node_id: str,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Update metrics for a node.
        
        Args:
            node_id: Node identifier
            metrics: Metrics dictionary
        """
        self.load_calculator.update_node_from_dict(node_id, metrics)
    
    def register_node(
        self,
        node_id: str,
        capacity: int,
        initial_count: int = 0
    ) -> None:
        """Register a node for load tracking."""
        self.load_calculator.update_node_from_dict(node_id, {
            "capacity": capacity,
            "document_count": initial_count,
            "is_healthy": True
        })
    
    def unregister_node(self, node_id: str) -> None:
        """Unregister a node."""
        self.load_calculator.remove_node(node_id)
    
    def set_document_selector(
        self,
        func: Callable[[str, int], Awaitable[List[str]]]
    ) -> None:
        """Set the document selection function."""
        self._document_selector = func
    
    def set_transfer_function(
        self,
        func: Callable[[str, str, List[str]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Set the document transfer function."""
        self.migration_handler.set_transfer_function(func)
    
    async def start_monitoring(self) -> None:
        """Start continuous load monitoring."""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started rebalancer monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop load monitoring."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped rebalancer monitoring")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._is_running:
            try:
                await self._check_and_rebalance()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.config.check_interval_sec)
    
    async def _check_and_rebalance(self) -> None:
        """Check load and trigger rebalance if needed."""
        if self._status != RebalanceStatus.IDLE:
            return
        
        if self.is_in_cooldown:
            return
        
        needs_rebalance, reason = self.load_calculator.needs_rebalancing()
        
        if needs_rebalance:
            logger.info(f"Rebalance triggered: {reason}")
            await self.execute_rebalance()
    
    async def execute_rebalance(self) -> RebalanceOperation:
        """
        Execute a rebalance operation.
        
        Returns:
            Completed rebalance operation
        """
        self._operation_counter += 1
        operation = RebalanceOperation(
            operation_id=f"rebal_{self._operation_counter}",
            status=RebalanceStatus.ANALYZING,
            started_at=datetime.utcnow()
        )
        self._current_operation = operation
        self._status = RebalanceStatus.ANALYZING
        
        try:
            # Analyze and plan
            logger.info(f"Operation {operation.operation_id}: Analyzing cluster")
            summary = self.load_calculator.calculate_cluster_summary()
            
            self._status = RebalanceStatus.PLANNING
            operation.status = RebalanceStatus.PLANNING
            
            decisions = self.load_calculator.generate_rebalance_plan()
            operation.decisions = decisions
            
            if not decisions:
                logger.info("No rebalance needed after analysis")
                operation.status = RebalanceStatus.COMPLETED
                operation.completed_at = datetime.utcnow()
                self._status = RebalanceStatus.IDLE
                return operation
            
            # Log plan
            impact = self.load_calculator.estimate_rebalance_impact(decisions)
            logger.info(f"Rebalance plan: {len(decisions)} migrations, "
                       f"{impact['total_documents_moved']} docs, "
                       f"~{impact['estimated_duration_sec']:.0f}s")
            
            # Execute migrations
            self._status = RebalanceStatus.EXECUTING
            operation.status = RebalanceStatus.EXECUTING
            
            for decision in decisions:
                if not self._is_running:
                    break
                
                result = await self._execute_decision(decision)
                
                if result:
                    operation.migration_tasks.append(result.task_id)
                    operation.documents_moved += result.documents_migrated
                    operation.documents_failed += result.documents_failed
            
            # Complete
            operation.status = RebalanceStatus.COMPLETED
            operation.completed_at = datetime.utcnow()
            self._last_rebalance = datetime.utcnow()
            
            logger.info(
                f"Rebalance completed: {operation.documents_moved} moved, "
                f"{operation.documents_failed} failed"
            )
            
        except Exception as e:
            logger.error(f"Rebalance failed: {e}")
            operation.status = RebalanceStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.utcnow()
        
        finally:
            self._status = RebalanceStatus.IDLE
            self._operation_history.append(operation)
            self._current_operation = None
        
        return operation
    
    async def _execute_decision(
        self,
        decision: RebalanceDecision
    ) -> Optional[MigrationResult]:
        """
        Execute a single rebalance decision.
        
        Args:
            decision: Rebalance decision to execute
            
        Returns:
            Migration result
        """
        if not decision.source_node or not decision.target_node:
            return None
        
        # Select documents to migrate
        doc_ids = await self._select_documents(
            decision.source_node,
            decision.documents_to_move
        )
        
        if not doc_ids:
            logger.warning(f"No documents selected for migration from {decision.source_node}")
            return None
        
        # Create and execute migration task
        task = self.migration_handler.create_task(
            source_node=decision.source_node,
            target_node=decision.target_node,
            document_ids=doc_ids
        )
        
        result = await self.migration_handler.execute_task(task.task_id)
        
        return result
    
    async def _select_documents(
        self,
        node_id: str,
        count: int
    ) -> List[str]:
        """
        Select documents for migration.
        
        Args:
            node_id: Node to select from
            count: Number to select
            
        Returns:
            List of document IDs
        """
        if self._document_selector:
            return await self._document_selector(node_id, count)
        
        # Fallback: return empty (requires selector to be set)
        logger.warning("No document selector set, cannot select documents")
        return []
    
    def pause(self) -> bool:
        """Pause rebalancing operations."""
        if self._status == RebalanceStatus.EXECUTING:
            self._status = RebalanceStatus.PAUSED
            return True
        return False
    
    def resume(self) -> bool:
        """Resume paused rebalancing."""
        if self._status == RebalanceStatus.PAUSED:
            self._status = RebalanceStatus.EXECUTING
            return True
        return False
    
    def get_current_operation(self) -> Optional[RebalanceOperation]:
        """Get the current rebalance operation."""
        return self._current_operation
    
    def get_cluster_summary(self) -> ClusterLoadSummary:
        """Get current cluster load summary."""
        return self.load_calculator.calculate_cluster_summary()
    
    def get_operation_history(self, limit: int = 20) -> List[RebalanceOperation]:
        """Get rebalance operation history."""
        return self._operation_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rebalancer statistics."""
        migration_stats = self.migration_handler.get_statistics()
        
        total_moved = sum(op.documents_moved for op in self._operation_history)
        total_failed = sum(op.documents_failed for op in self._operation_history)
        
        return {
            "status": self._status.value,
            "is_running": self._is_running,
            "is_in_cooldown": self.is_in_cooldown,
            "total_operations": len(self._operation_history),
            "total_documents_moved": total_moved,
            "total_documents_failed": total_failed,
            "last_rebalance": self._last_rebalance.isoformat() if self._last_rebalance else None,
            "migration_stats": migration_stats,
            "config": {
                "imbalance_threshold": self.config.imbalance_threshold,
                "batch_size": self.config.batch_size,
                "check_interval_sec": self.config.check_interval_sec
            }
        }
    
    def force_check(self) -> None:
        """Force an immediate load check (async trigger)."""
        if self._is_running and self._status == RebalanceStatus.IDLE:
            asyncio.create_task(self._check_and_rebalance())

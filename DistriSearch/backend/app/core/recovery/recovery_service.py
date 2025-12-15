# -*- coding: utf-8 -*-
"""
Recovery Service - Coordinates failure recovery operations.

Orchestrates:
- Failure detection response
- Replica promotion
- Data re-replication
- Node rejoining
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .failure_detector import FailureDetector, FailureEvent, NodeHealth, NodeStatus
from .re_replication import ReReplicationManager, ReReplicationTask

logger = logging.getLogger(__name__)


class RecoveryPhase(Enum):
    """Phases of recovery process."""
    DETECTION = "detection"
    ASSESSMENT = "assessment"
    PROMOTION = "promotion"
    RE_REPLICATION = "re_replication"
    VERIFICATION = "verification"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RecoveryConfig:
    """Configuration for recovery operations."""
    # Failure detection
    heartbeat_interval_sec: float = 5.0
    failure_timeout_sec: float = 15.0
    suspect_threshold: int = 2
    failure_threshold: int = 3
    
    # Re-replication
    max_concurrent_rereplications: int = 5
    re_replication_batch_size: int = 20
    re_replication_retry_limit: int = 3
    
    # Recovery timing
    assessment_delay_sec: float = 2.0
    verification_timeout_sec: float = 60.0


@dataclass
class RecoveryTask:
    """Represents a recovery operation for a failed node."""
    task_id: str
    failed_node: str
    phase: RecoveryPhase
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    affected_documents: List[str] = field(default_factory=list)
    promoted_primaries: Dict[str, str] = field(default_factory=dict)  # doc_id -> new_primary
    re_replication_tasks: List[str] = field(default_factory=list)
    documents_recovered: int = 0
    documents_failed: int = 0
    error: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        return self.phase in (RecoveryPhase.COMPLETED, RecoveryPhase.FAILED)
    
    @property
    def duration_sec(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.utcnow() - self.started_at).total_seconds()


class RecoveryService:
    """
    Coordinates failure detection and recovery.
    
    Workflow on node failure:
    1. Detect failure via missed heartbeats
    2. Assess impact (which documents affected)
    3. Promote replicas to primary where needed
    4. Re-replicate to maintain replication factor
    5. Verify recovery complete
    """
    
    def __init__(
        self,
        config: Optional[RecoveryConfig] = None,
        get_documents_on_node: Optional[Callable[[str], Awaitable[List[str]]]] = None,
        get_document_replicas: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
        promote_replica: Optional[Callable[[str, str], Awaitable[bool]]] = None,
        replicate_func: Optional[Callable[[str, str, str], Awaitable[bool]]] = None,
        select_target: Optional[Callable[[str, List[str]], Awaitable[Optional[str]]]] = None
    ):
        """
        Initialize recovery service.
        
        Args:
            config: Recovery configuration
            get_documents_on_node: Function to get documents on a node
            get_document_replicas: Function to get replica info
            promote_replica: Function to promote a replica to primary
            replicate_func: Function to replicate document
            select_target: Function to select target node
        """
        self.config = config or RecoveryConfig()
        
        # Callbacks
        self._get_docs_func = get_documents_on_node
        self._get_replicas_func = get_document_replicas
        self._promote_func = promote_replica
        self._replicate_func = replicate_func
        self._select_target_func = select_target
        
        # Initialize components
        self.failure_detector = FailureDetector(
            heartbeat_interval_sec=self.config.heartbeat_interval_sec,
            failure_timeout_sec=self.config.failure_timeout_sec,
            suspect_threshold=self.config.suspect_threshold,
            failure_threshold=self.config.failure_threshold,
            on_failure=self._handle_failure
        )
        
        self.re_replication_mgr = ReReplicationManager(
            replicate_func=replicate_func,
            get_document_replicas=get_document_replicas,
            select_target_node=select_target,
            max_concurrent=self.config.max_concurrent_rereplications,
            batch_size=self.config.re_replication_batch_size,
            retry_limit=self.config.re_replication_retry_limit
        )
        
        # State
        self._active_recoveries: Dict[str, RecoveryTask] = {}
        self._recovery_history: List[RecoveryTask] = []
        self._is_running = False
        self._task_counter = 0
    
    async def start(self) -> None:
        """Start the recovery service."""
        if self._is_running:
            return
        
        self._is_running = True
        await self.failure_detector.start_monitoring()
        await self.re_replication_mgr.start_processing()
        
        logger.info("Recovery service started")
    
    async def stop(self) -> None:
        """Stop the recovery service."""
        self._is_running = False
        
        await self.failure_detector.stop_monitoring()
        await self.re_replication_mgr.stop_processing()
        
        logger.info("Recovery service stopped")
    
    def register_node(self, node_id: str, metadata: Optional[Dict] = None) -> None:
        """Register a node for monitoring."""
        self.failure_detector.register_node(node_id, metadata)
    
    def unregister_node(self, node_id: str) -> None:
        """Unregister a node."""
        self.failure_detector.unregister_node(node_id)
    
    def record_heartbeat(
        self,
        node_id: str,
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record heartbeat from a node."""
        self.failure_detector.record_heartbeat(node_id, latency_ms, metadata)
    
    async def _handle_failure(self, event: FailureEvent) -> None:
        """
        Handle a node failure event.
        
        Args:
            event: Failure event
        """
        logger.error(f"Handling failure of node {event.node_id}")
        
        # Create recovery task
        self._task_counter += 1
        task = RecoveryTask(
            task_id=f"recovery_{self._task_counter}",
            failed_node=event.node_id,
            phase=RecoveryPhase.DETECTION
        )
        
        self._active_recoveries[task.task_id] = task
        
        try:
            # Execute recovery phases
            await self._execute_recovery(task)
            
        except Exception as e:
            logger.error(f"Recovery failed for {event.node_id}: {e}")
            task.phase = RecoveryPhase.FAILED
            task.error = str(e)
        
        finally:
            task.completed_at = datetime.utcnow()
            del self._active_recoveries[task.task_id]
            self._recovery_history.append(task)
    
    async def _execute_recovery(self, task: RecoveryTask) -> None:
        """
        Execute the full recovery workflow.
        
        Args:
            task: Recovery task
        """
        # Phase 1: Assessment
        task.phase = RecoveryPhase.ASSESSMENT
        await asyncio.sleep(self.config.assessment_delay_sec)  # Brief delay for cluster to stabilize
        
        affected_docs = await self._assess_impact(task.failed_node)
        task.affected_documents = affected_docs
        
        logger.info(f"Recovery assessment: {len(affected_docs)} documents affected")
        
        if not affected_docs:
            task.phase = RecoveryPhase.COMPLETED
            return
        
        # Phase 2: Promotion
        task.phase = RecoveryPhase.PROMOTION
        await self._promote_replicas(task)
        
        # Phase 3: Re-replication
        task.phase = RecoveryPhase.RE_REPLICATION
        await self._queue_re_replications(task)
        
        # Phase 4: Verification
        task.phase = RecoveryPhase.VERIFICATION
        await self._verify_recovery(task)
        
        task.phase = RecoveryPhase.COMPLETED
        logger.info(
            f"Recovery completed for {task.failed_node}: "
            f"{task.documents_recovered} recovered, {task.documents_failed} failed"
        )
    
    async def _assess_impact(self, node_id: str) -> List[str]:
        """
        Assess which documents are affected by node failure.
        
        Args:
            node_id: Failed node
            
        Returns:
            List of affected document IDs
        """
        if self._get_docs_func:
            return await self._get_docs_func(node_id)
        return []
    
    async def _promote_replicas(self, task: RecoveryTask) -> None:
        """
        Promote replicas to primary where the failed node was primary.
        
        Args:
            task: Recovery task
        """
        for doc_id in task.affected_documents:
            try:
                replica_info = await self._get_replica_info(doc_id)
                if not replica_info:
                    continue
                
                # Check if failed node was primary
                primary = replica_info.get("primary")
                if primary != task.failed_node:
                    continue
                
                # Find healthy replica to promote
                replicas = replica_info.get("replicas", [])
                healthy_replicas = [
                    r for r in replicas
                    if r.get("status") == "active" and r.get("node") != task.failed_node
                ]
                
                if healthy_replicas:
                    new_primary = healthy_replicas[0]["node"]
                    
                    if self._promote_func:
                        success = await self._promote_func(doc_id, new_primary)
                        if success:
                            task.promoted_primaries[doc_id] = new_primary
                            logger.info(f"Promoted {new_primary} to primary for {doc_id}")
                
            except Exception as e:
                logger.error(f"Failed to promote replica for {doc_id}: {e}")
    
    async def _get_replica_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get replica information."""
        if self._get_replicas_func:
            return await self._get_replicas_func(document_id)
        return None
    
    async def _queue_re_replications(self, task: RecoveryTask) -> None:
        """
        Queue re-replication for under-replicated documents.
        
        Args:
            task: Recovery task
        """
        re_rep_tasks = self.re_replication_mgr.queue_bulk_re_replication(
            document_ids=task.affected_documents,
            failed_node=task.failed_node,
            priority=2  # High priority for failure recovery
        )
        
        task.re_replication_tasks = [t.task_id for t in re_rep_tasks]
        logger.info(f"Queued {len(re_rep_tasks)} re-replication tasks")
    
    async def _verify_recovery(self, task: RecoveryTask) -> None:
        """
        Verify that recovery is complete.
        
        Args:
            task: Recovery task
        """
        # Wait for re-replications to complete (with timeout)
        timeout = self.config.verification_timeout_sec
        start = datetime.utcnow()
        
        while (datetime.utcnow() - start).total_seconds() < timeout:
            pending = self.re_replication_mgr.get_pending_count()
            active = self.re_replication_mgr.get_active_count()
            
            if pending == 0 and active == 0:
                break
            
            await asyncio.sleep(2.0)
        
        # Check statistics
        stats = self.re_replication_mgr.get_statistics()
        task.documents_recovered = stats["total_completed"]
        task.documents_failed = stats["total_failed"]
    
    async def trigger_manual_recovery(self, node_id: str) -> RecoveryTask:
        """
        Manually trigger recovery for a node.
        
        Args:
            node_id: Node to recover
            
        Returns:
            Recovery task
        """
        event = FailureEvent(
            node_id=node_id,
            detected_at=datetime.utcnow(),
            last_healthy=None,
            failure_type="manual"
        )
        
        await self._handle_failure(event)
        
        # Return the task from history
        for task in reversed(self._recovery_history):
            if task.failed_node == node_id:
                return task
        
        raise RuntimeError("Recovery task not found")
    
    def get_node_health(self, node_id: str) -> Optional[NodeHealth]:
        """Get health info for a node."""
        return self.failure_detector.get_node_health(node_id)
    
    def get_all_health(self) -> Dict[str, NodeHealth]:
        """Get health info for all nodes."""
        return self.failure_detector.get_all_health()
    
    def get_healthy_nodes(self) -> List[str]:
        """Get list of healthy nodes."""
        return self.failure_detector.get_healthy_nodes()
    
    def get_failed_nodes(self) -> List[str]:
        """Get list of failed nodes."""
        return self.failure_detector.get_failed_nodes()
    
    def get_active_recoveries(self) -> List[RecoveryTask]:
        """Get active recovery operations."""
        return list(self._active_recoveries.values())
    
    def get_recovery_history(self, limit: int = 20) -> List[RecoveryTask]:
        """Get recovery history."""
        return self._recovery_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        detector_stats = self.failure_detector.get_statistics()
        re_rep_stats = self.re_replication_mgr.get_statistics()
        
        total_recovered = sum(t.documents_recovered for t in self._recovery_history)
        total_failed = sum(t.documents_failed for t in self._recovery_history)
        
        return {
            "is_running": self._is_running,
            "active_recoveries": len(self._active_recoveries),
            "total_recoveries": len(self._recovery_history),
            "total_documents_recovered": total_recovered,
            "total_documents_failed": total_failed,
            "failure_detector": detector_stats,
            "re_replication": re_rep_stats
        }

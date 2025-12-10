# -*- coding: utf-8 -*-
"""
Re-Replication Manager - Handles re-replication of data after node failure.

Ensures data is re-replicated to maintain replication factor
after node failures.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReReplicationStatus(Enum):
    """Status of re-replication task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReReplicationTask:
    """Task to re-replicate a document."""
    task_id: str
    document_id: str
    failed_node: str
    source_node: Optional[str] = None
    target_node: Optional[str] = None
    status: ReReplicationStatus = ReReplicationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    priority: int = 1  # Higher = more urgent


class ReReplicationManager:
    """
    Manages re-replication of data after failures.
    
    When a node fails:
    1. Identifies all documents that were stored on that node
    2. For each document, finds a healthy replica
    3. Replicates to a new node to maintain replication factor
    """
    
    def __init__(
        self,
        replicate_func: Optional[Callable[[str, str, str], Awaitable[bool]]] = None,
        get_document_replicas: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
        select_target_node: Optional[Callable[[str, List[str]], Awaitable[Optional[str]]]] = None,
        max_concurrent: int = 5,
        batch_size: int = 20,
        retry_limit: int = 3
    ):
        """
        Initialize re-replication manager.
        
        Args:
            replicate_func: Function to replicate document
            get_document_replicas: Function to get document replica info
            select_target_node: Function to select target node for new replica
            max_concurrent: Maximum concurrent re-replications
            batch_size: Documents to process per batch
            retry_limit: Maximum retries per document
        """
        self._replicate_func = replicate_func
        self._get_replicas_func = get_document_replicas
        self._select_target_func = select_target_node
        
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.retry_limit = retry_limit
        
        # Task tracking
        self._pending_tasks: Dict[str, ReReplicationTask] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: List[ReReplicationTask] = []
        
        # State
        self._is_running = False
        self._process_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._total_completed = 0
        self._total_failed = 0
    
    def set_replicate_function(
        self,
        func: Callable[[str, str, str], Awaitable[bool]]
    ) -> None:
        """Set the replication function."""
        self._replicate_func = func
    
    def set_get_replicas_function(
        self,
        func: Callable[[str], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Set function to get document replicas."""
        self._get_replicas_func = func
    
    def set_target_selector(
        self,
        func: Callable[[str, List[str]], Awaitable[Optional[str]]]
    ) -> None:
        """Set function to select target node."""
        self._select_target_func = func
    
    def queue_re_replication(
        self,
        document_id: str,
        failed_node: str,
        priority: int = 1
    ) -> ReReplicationTask:
        """
        Queue a document for re-replication.
        
        Args:
            document_id: Document to re-replicate
            failed_node: Node that failed
            priority: Task priority (higher = more urgent)
            
        Returns:
            Created task
        """
        task_id = f"rerep_{document_id}_{datetime.utcnow().timestamp()}"
        
        task = ReReplicationTask(
            task_id=task_id,
            document_id=document_id,
            failed_node=failed_node,
            priority=priority
        )
        
        self._pending_tasks[task_id] = task
        logger.debug(f"Queued re-replication for {document_id}")
        
        return task
    
    def queue_bulk_re_replication(
        self,
        document_ids: List[str],
        failed_node: str,
        priority: int = 1
    ) -> List[ReReplicationTask]:
        """
        Queue multiple documents for re-replication.
        
        Args:
            document_ids: Documents to re-replicate
            failed_node: Node that failed
            priority: Task priority
            
        Returns:
            Created tasks
        """
        tasks = []
        for doc_id in document_ids:
            task = self.queue_re_replication(doc_id, failed_node, priority)
            tasks.append(task)
        
        logger.info(f"Queued {len(tasks)} documents for re-replication from {failed_node}")
        return tasks
    
    async def start_processing(self) -> None:
        """Start processing re-replication queue."""
        if self._is_running:
            return
        
        self._is_running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Started re-replication processing")
    
    async def stop_processing(self) -> None:
        """Stop processing."""
        self._is_running = False
        
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active tasks
        for task in self._active_tasks.values():
            task.cancel()
        
        logger.info("Stopped re-replication processing")
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._is_running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Re-replication loop error: {e}")
            
            await asyncio.sleep(1.0)
    
    async def _process_batch(self) -> None:
        """Process a batch of pending tasks."""
        # Get available slots
        available = self.max_concurrent - len(self._active_tasks)
        if available <= 0:
            return
        
        # Sort by priority and get batch
        sorted_tasks = sorted(
            self._pending_tasks.values(),
            key=lambda t: t.priority,
            reverse=True
        )
        
        batch = sorted_tasks[:min(available, self.batch_size)]
        
        for task in batch:
            if task.task_id not in self._active_tasks:
                self._active_tasks[task.task_id] = asyncio.create_task(
                    self._execute_task(task)
                )
    
    async def _execute_task(self, task: ReReplicationTask) -> bool:
        """
        Execute a re-replication task.
        
        Args:
            task: Task to execute
            
        Returns:
            True if successful
        """
        task.started_at = datetime.utcnow()
        task.status = ReReplicationStatus.IN_PROGRESS
        
        try:
            # Get replica info
            replica_info = await self._get_replica_info(task.document_id)
            if not replica_info:
                raise RuntimeError(f"No replica info for {task.document_id}")
            
            # Find healthy source
            task.source_node = await self._find_healthy_source(
                task.document_id,
                replica_info,
                task.failed_node
            )
            if not task.source_node:
                raise RuntimeError("No healthy source replica")
            
            # Select target node
            exclude = replica_info.get("nodes", [])
            task.target_node = await self._select_target(
                task.document_id,
                exclude
            )
            if not task.target_node:
                raise RuntimeError("No available target node")
            
            # Perform replication
            success = await self._do_replicate(
                task.document_id,
                task.source_node,
                task.target_node
            )
            
            if success:
                task.status = ReReplicationStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                self._total_completed += 1
                logger.info(
                    f"Re-replicated {task.document_id}: "
                    f"{task.source_node} -> {task.target_node}"
                )
            else:
                raise RuntimeError("Replication failed")
            
            return True
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count < self.retry_limit:
                task.status = ReReplicationStatus.PENDING
                logger.warning(
                    f"Re-replication failed for {task.document_id}, "
                    f"retry {task.retry_count}/{self.retry_limit}: {e}"
                )
            else:
                task.status = ReReplicationStatus.FAILED
                task.completed_at = datetime.utcnow()
                self._total_failed += 1
                logger.error(
                    f"Re-replication permanently failed for {task.document_id}: {e}"
                )
            
            return False
        
        finally:
            # Clean up
            self._pending_tasks.pop(task.task_id, None)
            self._active_tasks.pop(task.task_id, None)
            
            if task.status in (ReReplicationStatus.COMPLETED, ReReplicationStatus.FAILED):
                self._completed_tasks.append(task)
                # Keep limited history
                if len(self._completed_tasks) > 1000:
                    self._completed_tasks = self._completed_tasks[-500:]
    
    async def _get_replica_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get replica information for a document."""
        if self._get_replicas_func:
            return await self._get_replicas_func(document_id)
        return None
    
    async def _find_healthy_source(
        self,
        document_id: str,
        replica_info: Dict[str, Any],
        failed_node: str
    ) -> Optional[str]:
        """Find a healthy node with the document."""
        nodes = replica_info.get("nodes", [])
        healthy = replica_info.get("healthy_nodes", nodes)
        
        for node in healthy:
            if node != failed_node:
                return node
        
        return None
    
    async def _select_target(
        self,
        document_id: str,
        exclude_nodes: List[str]
    ) -> Optional[str]:
        """Select target node for new replica."""
        if self._select_target_func:
            return await self._select_target_func(document_id, exclude_nodes)
        return None
    
    async def _do_replicate(
        self,
        document_id: str,
        source: str,
        target: str
    ) -> bool:
        """Perform the actual replication."""
        if self._replicate_func:
            return await self._replicate_func(document_id, source, target)
        
        # Mock
        await asyncio.sleep(0.1)
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._pending_tasks.get(task_id)
        if task:
            task.status = ReReplicationStatus.CANCELLED
            del self._pending_tasks[task_id]
            return True
        
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            return True
        
        return False
    
    def get_pending_count(self) -> int:
        """Get number of pending tasks."""
        return len(self._pending_tasks)
    
    def get_active_count(self) -> int:
        """Get number of active tasks."""
        return len(self._active_tasks)
    
    def get_task(self, task_id: str) -> Optional[ReReplicationTask]:
        """Get a task by ID."""
        return (
            self._pending_tasks.get(task_id) or
            self._completed_tasks[-1] if self._completed_tasks and 
                self._completed_tasks[-1].task_id == task_id else None
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get re-replication statistics."""
        return {
            "is_running": self._is_running,
            "pending_tasks": len(self._pending_tasks),
            "active_tasks": len(self._active_tasks),
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "success_rate": (
                self._total_completed / (self._total_completed + self._total_failed)
                if (self._total_completed + self._total_failed) > 0 else 0.0
            )
        }

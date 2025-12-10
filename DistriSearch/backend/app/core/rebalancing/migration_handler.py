# -*- coding: utf-8 -*-
"""
Migration Handler - Handles document migration between nodes.

Implements batch transfers with rate limiting as specified:
"batch transfers (50 docs/batch) with rate limiting (1s sleep between batches)"
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Status of a migration task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class MigrationTask:
    """Represents a document migration task."""
    task_id: str
    source_node: str
    target_node: str
    document_ids: List[str]
    status: MigrationStatus = MigrationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    documents_migrated: int = 0
    documents_failed: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def total_documents(self) -> int:
        return len(self.document_ids)
    
    @property
    def is_complete(self) -> bool:
        return self.status in (MigrationStatus.COMPLETED, MigrationStatus.FAILED, MigrationStatus.CANCELLED)
    
    @property
    def duration_sec(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    task_id: str
    success: bool
    documents_migrated: int
    documents_failed: int
    duration_sec: float
    error_message: Optional[str] = None
    failed_documents: List[str] = field(default_factory=list)


@dataclass 
class MigrationConfig:
    """Configuration for migration operations."""
    batch_size: int = 50  # docs per batch as per spec
    batch_delay_sec: float = 1.0  # sleep between batches as per spec
    max_concurrent_batches: int = 1
    max_retries: int = 3
    retry_delay_sec: float = 5.0
    transfer_timeout_sec: float = 30.0


class MigrationHandler:
    """
    Handles document migrations between cluster nodes.
    
    Implements:
    - Batch transfers (50 docs/batch per architecture spec)
    - Rate limiting (1s sleep between batches)
    - Progress tracking
    - Retry logic
    - Cancellation support
    """
    
    def __init__(
        self,
        config: Optional[MigrationConfig] = None,
        transfer_func: Optional[Callable[[str, str, List[str]], Awaitable[Dict[str, Any]]]] = None
    ):
        """
        Initialize migration handler.
        
        Args:
            config: Migration configuration
            transfer_func: Async function to actually transfer documents
                          Signature: (source_node, target_node, doc_ids) -> result
        """
        self.config = config or MigrationConfig()
        self._transfer_func = transfer_func
        
        self._tasks: Dict[str, MigrationTask] = {}
        self._active_migrations: Dict[str, asyncio.Task] = {}
        self._cancelled: set = set()
        
        self._total_migrated = 0
        self._total_failed = 0
    
    def set_transfer_function(
        self,
        func: Callable[[str, str, List[str]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Set the document transfer function."""
        self._transfer_func = func
    
    def create_task(
        self,
        source_node: str,
        target_node: str,
        document_ids: List[str]
    ) -> MigrationTask:
        """
        Create a migration task.
        
        Args:
            source_node: Node to migrate from
            target_node: Node to migrate to
            document_ids: Documents to migrate
            
        Returns:
            Created migration task
        """
        task_id = f"mig_{uuid.uuid4().hex[:12]}"
        
        task = MigrationTask(
            task_id=task_id,
            source_node=source_node,
            target_node=target_node,
            document_ids=document_ids,
            max_retries=self.config.max_retries
        )
        
        self._tasks[task_id] = task
        logger.info(
            f"Created migration task {task_id}: "
            f"{len(document_ids)} docs from {source_node} to {target_node}"
        )
        
        return task
    
    async def execute_task(self, task_id: str) -> MigrationResult:
        """
        Execute a migration task.
        
        Args:
            task_id: Task to execute
            
        Returns:
            Migration result
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        
        if task.is_complete:
            raise ValueError(f"Task already complete: {task_id}")
        
        task.status = MigrationStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        
        logger.info(f"Starting migration task {task_id}")
        
        try:
            result = await self._execute_migration(task)
            return result
        except Exception as e:
            logger.error(f"Migration task {task_id} failed: {e}")
            task.status = MigrationStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            
            return MigrationResult(
                task_id=task_id,
                success=False,
                documents_migrated=task.documents_migrated,
                documents_failed=task.total_documents - task.documents_migrated,
                duration_sec=task.duration_sec or 0.0,
                error_message=str(e)
            )
    
    async def _execute_migration(self, task: MigrationTask) -> MigrationResult:
        """
        Execute the actual migration with batching and rate limiting.
        
        Args:
            task: Migration task to execute
            
        Returns:
            Migration result
        """
        failed_docs = []
        
        # Split into batches
        batches = [
            task.document_ids[i:i + self.config.batch_size]
            for i in range(0, len(task.document_ids), self.config.batch_size)
        ]
        
        total_batches = len(batches)
        logger.info(f"Task {task.task_id}: {total_batches} batches of up to {self.config.batch_size} docs")
        
        for batch_idx, batch in enumerate(batches):
            # Check for cancellation
            if task.task_id in self._cancelled:
                task.status = MigrationStatus.CANCELLED
                task.completed_at = datetime.utcnow()
                break
            
            # Execute batch transfer
            try:
                batch_result = await self._transfer_batch(
                    task.source_node,
                    task.target_node,
                    batch
                )
                
                migrated = batch_result.get("migrated", [])
                failed = batch_result.get("failed", [])
                
                task.documents_migrated += len(migrated)
                task.documents_failed += len(failed)
                failed_docs.extend(failed)
                
            except Exception as e:
                logger.error(f"Batch {batch_idx} failed: {e}")
                
                # Retry logic
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    await asyncio.sleep(self.config.retry_delay_sec)
                    
                    try:
                        batch_result = await self._transfer_batch(
                            task.source_node,
                            task.target_node,
                            batch
                        )
                        task.documents_migrated += len(batch_result.get("migrated", []))
                    except Exception:
                        task.documents_failed += len(batch)
                        failed_docs.extend(batch)
                else:
                    task.documents_failed += len(batch)
                    failed_docs.extend(batch)
            
            # Update progress
            task.progress = (batch_idx + 1) / total_batches
            
            # Rate limiting: sleep between batches
            if batch_idx < total_batches - 1:
                await asyncio.sleep(self.config.batch_delay_sec)
        
        # Finalize
        if task.status != MigrationStatus.CANCELLED:
            if task.documents_failed == 0:
                task.status = MigrationStatus.COMPLETED
            elif task.documents_migrated > 0:
                task.status = MigrationStatus.COMPLETED  # Partial success
            else:
                task.status = MigrationStatus.FAILED
        
        task.completed_at = datetime.utcnow()
        task.progress = 1.0
        
        # Update totals
        self._total_migrated += task.documents_migrated
        self._total_failed += task.documents_failed
        
        logger.info(
            f"Task {task.task_id} finished: {task.documents_migrated} migrated, "
            f"{task.documents_failed} failed, status={task.status.value}"
        )
        
        return MigrationResult(
            task_id=task.task_id,
            success=task.documents_failed == 0,
            documents_migrated=task.documents_migrated,
            documents_failed=task.documents_failed,
            duration_sec=task.duration_sec or 0.0,
            failed_documents=failed_docs
        )
    
    async def _transfer_batch(
        self,
        source: str,
        target: str,
        doc_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Transfer a batch of documents.
        
        Args:
            source: Source node
            target: Target node
            doc_ids: Document IDs to transfer
            
        Returns:
            Transfer result with migrated/failed lists
        """
        if self._transfer_func:
            return await asyncio.wait_for(
                self._transfer_func(source, target, doc_ids),
                timeout=self.config.transfer_timeout_sec
            )
        
        # Mock implementation for testing
        logger.warning("No transfer function set, using mock")
        await asyncio.sleep(0.1)  # Simulate transfer time
        return {"migrated": doc_ids, "failed": []}
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a migration task.
        
        Args:
            task_id: Task to cancel
            
        Returns:
            True if cancelled
        """
        task = self._tasks.get(task_id)
        if not task or task.is_complete:
            return False
        
        self._cancelled.add(task_id)
        
        # Cancel asyncio task if running
        if task_id in self._active_migrations:
            self._active_migrations[task_id].cancel()
        
        logger.info(f"Cancelled migration task {task_id}")
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a migration task (not yet implemented)."""
        task = self._tasks.get(task_id)
        if task and task.status == MigrationStatus.IN_PROGRESS:
            task.status = MigrationStatus.PAUSED
            return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused migration task (not yet implemented)."""
        task = self._tasks.get(task_id)
        if task and task.status == MigrationStatus.PAUSED:
            task.status = MigrationStatus.IN_PROGRESS
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[MigrationTask]:
        """Get a migration task by ID."""
        return self._tasks.get(task_id)
    
    def get_active_tasks(self) -> List[MigrationTask]:
        """Get all active (non-complete) tasks."""
        return [
            t for t in self._tasks.values()
            if not t.is_complete
        ]
    
    def get_task_history(self, limit: int = 100) -> List[MigrationTask]:
        """Get completed tasks."""
        completed = [t for t in self._tasks.values() if t.is_complete]
        completed.sort(key=lambda t: t.completed_at or datetime.min, reverse=True)
        return completed[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get migration statistics."""
        active = self.get_active_tasks()
        completed = [t for t in self._tasks.values() if t.status == MigrationStatus.COMPLETED]
        failed = [t for t in self._tasks.values() if t.status == MigrationStatus.FAILED]
        
        return {
            "total_tasks": len(self._tasks),
            "active_tasks": len(active),
            "completed_tasks": len(completed),
            "failed_tasks": len(failed),
            "total_documents_migrated": self._total_migrated,
            "total_documents_failed": self._total_failed,
            "current_progress": sum(t.progress for t in active) / len(active) if active else 0.0
        }
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed tasks.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of tasks removed
        """
        cutoff = datetime.utcnow()
        removed = 0
        
        for task_id, task in list(self._tasks.items()):
            if task.is_complete and task.completed_at:
                age = (cutoff - task.completed_at).total_seconds() / 3600
                if age > max_age_hours:
                    del self._tasks[task_id]
                    removed += 1
        
        return removed

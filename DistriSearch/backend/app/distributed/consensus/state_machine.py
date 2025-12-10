"""
State Machine for Raft.

Implements the replicated state machine that applies
committed log entries. This is where the actual
cluster state changes happen.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable, List

from app.distributed.consensus.raft_state import RaftState
from app.distributed.consensus.log_entry import LogStore, LogEntry

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands that can be applied to state machine."""
    
    # Cluster membership
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_NODE = "update_node"
    
    # Document operations
    ADD_DOCUMENT = "add_document"
    REMOVE_DOCUMENT = "remove_document"
    UPDATE_DOCUMENT = "update_document"
    
    # Partition operations
    ASSIGN_PARTITION = "assign_partition"
    MOVE_PARTITION = "move_partition"
    REBALANCE = "rebalance"
    
    # Replication operations
    ADD_REPLICA = "add_replica"
    REMOVE_REPLICA = "remove_replica"
    PROMOTE_REPLICA = "promote_replica"
    
    # Configuration
    UPDATE_CONFIG = "update_config"
    
    # No-op (for leader commitment)
    NOOP = "noop"


@dataclass
class Command:
    """
    A command to be applied to the state machine.
    
    Attributes:
        type: Type of command
        data: Command-specific data
        request_id: Optional client request ID for deduplication
    """
    type: CommandType
    data: Dict[str, Any]
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "data": self.data,
            "request_id": self.request_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Command":
        """Create from dictionary."""
        return cls(
            type=CommandType(data["type"]),
            data=data.get("data", {}),
            request_id=data.get("request_id"),
        )


# Type for command handlers
CommandHandler = Callable[[Command], Awaitable[Any]]


class StateMachine:
    """
    Replicated state machine for DistriSearch.
    
    Applies committed log entries to maintain consistent
    cluster state across all nodes.
    """
    
    def __init__(
        self,
        state: RaftState,
        log_store: LogStore,
    ):
        """
        Initialize state machine.
        
        Args:
            state: Raft state manager
            log_store: Log entry storage
        """
        self.state = state
        self.log_store = log_store
        
        # Command handlers by type
        self._handlers: Dict[CommandType, CommandHandler] = {}
        
        # Cluster state (replicated across all nodes)
        self._cluster_state: Dict[str, Any] = {
            "nodes": {},           # node_id -> NodeInfo
            "documents": {},       # doc_id -> DocumentMeta
            "partitions": {},      # partition_id -> PartitionInfo
            "replicas": {},        # doc_id -> List[node_id]
            "config": {},          # Configuration key-values
        }
        
        # Applied request IDs (for deduplication)
        self._applied_requests: Dict[str, Any] = {}
        self._max_applied_requests = 10000
        
        # Background apply task
        self._apply_task: Optional[asyncio.Task] = None
        self._apply_event = asyncio.Event()
        
        # Lock for state modifications
        self._lock = asyncio.Lock()
        
        # Register default handlers
        self._register_default_handlers()
        
        logger.info(f"StateMachine initialized for node {state.node_id}")
    
    def _register_default_handlers(self):
        """Register default command handlers."""
        self._handlers[CommandType.ADD_NODE] = self._handle_add_node
        self._handlers[CommandType.REMOVE_NODE] = self._handle_remove_node
        self._handlers[CommandType.UPDATE_NODE] = self._handle_update_node
        self._handlers[CommandType.ADD_DOCUMENT] = self._handle_add_document
        self._handlers[CommandType.REMOVE_DOCUMENT] = self._handle_remove_document
        self._handlers[CommandType.ASSIGN_PARTITION] = self._handle_assign_partition
        self._handlers[CommandType.MOVE_PARTITION] = self._handle_move_partition
        self._handlers[CommandType.ADD_REPLICA] = self._handle_add_replica
        self._handlers[CommandType.REMOVE_REPLICA] = self._handle_remove_replica
        self._handlers[CommandType.UPDATE_CONFIG] = self._handle_update_config
        self._handlers[CommandType.NOOP] = self._handle_noop
    
    def register_handler(
        self,
        command_type: CommandType,
        handler: CommandHandler,
    ):
        """
        Register a custom command handler.
        
        Args:
            command_type: Type of command to handle
            handler: Async function to handle the command
        """
        self._handlers[command_type] = handler
    
    async def start(self):
        """Start the state machine apply loop."""
        if self._apply_task and not self._apply_task.done():
            return
        
        self._apply_task = asyncio.create_task(self._apply_loop())
        logger.info("State machine apply loop started")
    
    async def stop(self):
        """Stop the state machine apply loop."""
        if self._apply_task and not self._apply_task.done():
            self._apply_task.cancel()
            try:
                await self._apply_task
            except asyncio.CancelledError:
                pass
        self._apply_task = None
    
    def trigger_apply(self):
        """Trigger the apply loop to check for new commits."""
        self._apply_event.set()
    
    async def _apply_loop(self):
        """
        Background loop that applies committed entries.
        
        Checks for entries between last_applied and commit_index
        and applies them to the state machine.
        """
        try:
            while True:
                # Wait for trigger or periodic check
                try:
                    await asyncio.wait_for(
                        self._apply_event.wait(),
                        timeout=0.1,
                    )
                    self._apply_event.clear()
                except asyncio.TimeoutError:
                    pass
                
                # Apply pending entries
                await self._apply_committed_entries()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in apply loop: {e}")
    
    async def _apply_committed_entries(self):
        """Apply all committed but not yet applied entries."""
        while self.state.volatile.last_applied < self.state.volatile.commit_index:
            next_index = self.state.volatile.last_applied + 1
            
            entry = await self.log_store.get_entry(next_index)
            if entry is None:
                logger.warning(f"Missing log entry at index {next_index}")
                break
            
            await self._apply_entry(entry)
            await self.state.update_last_applied(next_index)
    
    async def _apply_entry(self, entry: LogEntry):
        """
        Apply a single log entry to the state machine.
        
        Args:
            entry: The log entry to apply
        """
        try:
            command = Command.from_dict(entry.command)
            
            # Check for duplicate request
            if command.request_id:
                if command.request_id in self._applied_requests:
                    logger.debug(
                        f"Skipping duplicate request {command.request_id}"
                    )
                    return
            
            # Find handler
            handler = self._handlers.get(command.type)
            if handler is None:
                logger.warning(f"No handler for command type {command.type}")
                return
            
            # Apply command
            async with self._lock:
                result = await handler(command)
            
            # Record applied request
            if command.request_id:
                self._applied_requests[command.request_id] = result
                # Prune old requests
                if len(self._applied_requests) > self._max_applied_requests:
                    oldest = list(self._applied_requests.keys())[
                        :len(self._applied_requests) - self._max_applied_requests
                    ]
                    for key in oldest:
                        del self._applied_requests[key]
            
            logger.debug(
                f"Applied entry {entry.index}: {command.type.value}"
            )
            
        except Exception as e:
            logger.error(f"Error applying entry {entry.index}: {e}")
    
    # Default command handlers
    
    async def _handle_add_node(self, command: Command) -> Any:
        """Handle ADD_NODE command."""
        node_id = command.data.get("node_id")
        node_info = command.data.get("node_info", {})
        
        if node_id:
            self._cluster_state["nodes"][node_id] = {
                "id": node_id,
                "address": node_info.get("address"),
                "role": node_info.get("role", "slave"),
                "status": "active",
                **node_info,
            }
            
            # Update Raft cluster membership
            address = node_info.get("address")
            if address:
                await self.state.add_cluster_node(node_id, address)
            
            logger.info(f"Added node {node_id} to cluster")
        
        return {"success": True, "node_id": node_id}
    
    async def _handle_remove_node(self, command: Command) -> Any:
        """Handle REMOVE_NODE command."""
        node_id = command.data.get("node_id")
        
        if node_id and node_id in self._cluster_state["nodes"]:
            del self._cluster_state["nodes"][node_id]
            await self.state.remove_cluster_node(node_id)
            logger.info(f"Removed node {node_id} from cluster")
        
        return {"success": True, "node_id": node_id}
    
    async def _handle_update_node(self, command: Command) -> Any:
        """Handle UPDATE_NODE command."""
        node_id = command.data.get("node_id")
        updates = command.data.get("updates", {})
        
        if node_id and node_id in self._cluster_state["nodes"]:
            self._cluster_state["nodes"][node_id].update(updates)
            logger.info(f"Updated node {node_id}: {updates}")
        
        return {"success": True, "node_id": node_id}
    
    async def _handle_add_document(self, command: Command) -> Any:
        """Handle ADD_DOCUMENT command."""
        doc_id = command.data.get("doc_id")
        doc_meta = command.data.get("metadata", {})
        
        if doc_id:
            self._cluster_state["documents"][doc_id] = {
                "id": doc_id,
                "primary_node": doc_meta.get("primary_node"),
                "partition_id": doc_meta.get("partition_id"),
                **doc_meta,
            }
            logger.debug(f"Added document {doc_id} to state")
        
        return {"success": True, "doc_id": doc_id}
    
    async def _handle_remove_document(self, command: Command) -> Any:
        """Handle REMOVE_DOCUMENT command."""
        doc_id = command.data.get("doc_id")
        
        if doc_id:
            self._cluster_state["documents"].pop(doc_id, None)
            self._cluster_state["replicas"].pop(doc_id, None)
            logger.debug(f"Removed document {doc_id} from state")
        
        return {"success": True, "doc_id": doc_id}
    
    async def _handle_assign_partition(self, command: Command) -> Any:
        """Handle ASSIGN_PARTITION command."""
        partition_id = command.data.get("partition_id")
        node_id = command.data.get("node_id")
        doc_ids = command.data.get("doc_ids", [])
        
        if partition_id:
            self._cluster_state["partitions"][partition_id] = {
                "id": partition_id,
                "node_id": node_id,
                "doc_ids": doc_ids,
            }
            logger.info(
                f"Assigned partition {partition_id} to node {node_id}"
            )
        
        return {"success": True, "partition_id": partition_id}
    
    async def _handle_move_partition(self, command: Command) -> Any:
        """Handle MOVE_PARTITION command."""
        partition_id = command.data.get("partition_id")
        from_node = command.data.get("from_node")
        to_node = command.data.get("to_node")
        
        if partition_id and partition_id in self._cluster_state["partitions"]:
            self._cluster_state["partitions"][partition_id]["node_id"] = to_node
            logger.info(
                f"Moved partition {partition_id} from {from_node} to {to_node}"
            )
        
        return {"success": True, "partition_id": partition_id}
    
    async def _handle_add_replica(self, command: Command) -> Any:
        """Handle ADD_REPLICA command."""
        doc_id = command.data.get("doc_id")
        node_id = command.data.get("node_id")
        
        if doc_id and node_id:
            if doc_id not in self._cluster_state["replicas"]:
                self._cluster_state["replicas"][doc_id] = []
            
            if node_id not in self._cluster_state["replicas"][doc_id]:
                self._cluster_state["replicas"][doc_id].append(node_id)
                logger.debug(f"Added replica of {doc_id} on {node_id}")
        
        return {"success": True, "doc_id": doc_id, "node_id": node_id}
    
    async def _handle_remove_replica(self, command: Command) -> Any:
        """Handle REMOVE_REPLICA command."""
        doc_id = command.data.get("doc_id")
        node_id = command.data.get("node_id")
        
        if doc_id and doc_id in self._cluster_state["replicas"]:
            if node_id in self._cluster_state["replicas"][doc_id]:
                self._cluster_state["replicas"][doc_id].remove(node_id)
                logger.debug(f"Removed replica of {doc_id} from {node_id}")
        
        return {"success": True, "doc_id": doc_id, "node_id": node_id}
    
    async def _handle_update_config(self, command: Command) -> Any:
        """Handle UPDATE_CONFIG command."""
        key = command.data.get("key")
        value = command.data.get("value")
        
        if key:
            self._cluster_state["config"][key] = value
            logger.info(f"Updated config {key} = {value}")
        
        return {"success": True, "key": key}
    
    async def _handle_noop(self, command: Command) -> Any:
        """Handle NOOP command (used for leader commitment)."""
        return {"success": True}
    
    # State access methods
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node information."""
        return self._cluster_state["nodes"].get(node_id)
    
    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get all node information."""
        return self._cluster_state["nodes"].copy()
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata."""
        return self._cluster_state["documents"].get(doc_id)
    
    def get_partition(self, partition_id: str) -> Optional[Dict[str, Any]]:
        """Get partition information."""
        return self._cluster_state["partitions"].get(partition_id)
    
    def get_document_replicas(self, doc_id: str) -> List[str]:
        """Get nodes holding replicas of a document."""
        return self._cluster_state["replicas"].get(doc_id, [])
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._cluster_state["config"].get(key, default)
    
    def get_full_state(self) -> Dict[str, Any]:
        """Get complete cluster state."""
        return {
            "nodes": self._cluster_state["nodes"].copy(),
            "documents": len(self._cluster_state["documents"]),
            "partitions": self._cluster_state["partitions"].copy(),
            "config": self._cluster_state["config"].copy(),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get state machine status for monitoring."""
        return {
            "last_applied": self.state.volatile.last_applied,
            "commit_index": self.state.volatile.commit_index,
            "nodes_count": len(self._cluster_state["nodes"]),
            "documents_count": len(self._cluster_state["documents"]),
            "partitions_count": len(self._cluster_state["partitions"]),
            "apply_loop_active": (
                self._apply_task is not None and
                not self._apply_task.done()
            ),
        }

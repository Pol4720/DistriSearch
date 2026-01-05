"""
In-Memory State Machine for Raft.

This is the base state machine that applies committed log entries
to an in-memory state. Used for testing and as a base class for
the persistent state machine.

For production AP-mode, use PersistentStateMachine instead.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable, List

from .raft_state import RaftState
from .log_entry import LogStore, LogEntry

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands that can be applied to state machine."""
    
    # Cluster membership
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_NODE = "update_node"
    
    # User operations
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    
    # Document registry operations
    REGISTER_DOCUMENT = "register_document"
    UNREGISTER_DOCUMENT = "unregister_document"
    
    # Partition operations
    ASSIGN_PARTITION = "assign_partition"
    MOVE_PARTITION = "move_partition"
    REBALANCE = "rebalance"
    
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
    In-memory state machine for Raft consensus.
    
    Applies committed log entries to maintain cluster state.
    This is a base implementation that stores state in memory.
    
    For production use with persistence, use PersistentStateMachine.
    """
    
    def __init__(
        self,
        state: RaftState,
        log_store: LogStore,
    ):
        """
        Initialize state machine.
        
        Args:
            state: Raft state (for commit index)
            log_store: Log store for reading entries
        """
        self._state = state
        self._log_store = log_store
        
        # Last applied index (starts at 0, first real entry is 1)
        self._last_applied: int = 0
        
        # In-memory state
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._users: Dict[str, Dict[str, Any]] = {}
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._partitions: Dict[str, Dict[str, Any]] = {}
        self._config: Dict[str, Any] = {}
        
        # Custom command handlers
        self._handlers: Dict[CommandType, CommandHandler] = {}
        
        # Apply trigger event
        self._apply_event = asyncio.Event()
        self._running = False
        self._apply_task: Optional[asyncio.Task] = None
        
        logger.info("StateMachine initialized")
    
    async def start(self):
        """Start the state machine apply loop."""
        if self._running:
            return
        
        self._running = True
        self._apply_task = asyncio.create_task(self._apply_loop())
        logger.info("StateMachine started")
    
    async def stop(self):
        """Stop the state machine apply loop."""
        if not self._running:
            return
        
        self._running = False
        self._apply_event.set()  # Unblock the loop
        
        if self._apply_task:
            self._apply_task.cancel()
            try:
                await self._apply_task
            except asyncio.CancelledError:
                pass
        
        logger.info("StateMachine stopped")
    
    def trigger_apply(self):
        """Trigger the apply loop to check for new committed entries."""
        self._apply_event.set()
    
    async def _apply_loop(self):
        """Background loop that applies committed entries."""
        while self._running:
            try:
                # Wait for trigger or timeout
                try:
                    await asyncio.wait_for(
                        self._apply_event.wait(),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    pass
                
                self._apply_event.clear()
                
                # Apply all committed entries up to commit_index
                await self._apply_committed_entries()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in apply loop: {e}")
                await asyncio.sleep(0.1)
    
    async def _apply_committed_entries(self):
        """Apply all committed entries that haven't been applied yet."""
        commit_index = self._state.commit_index
        
        while self._last_applied < commit_index:
            next_index = self._last_applied + 1
            entry = await self._log_store.get_entry(next_index)
            
            if entry is None:
                logger.warning(f"Entry {next_index} not found")
                break
            
            await self._apply_entry(entry)
            self._last_applied = next_index
    
    async def _apply_entry(self, entry: LogEntry):
        """
        Apply a single log entry to the state machine.
        
        Args:
            entry: Log entry to apply
        """
        try:
            command = Command.from_dict(entry.command)
            
            # Check for custom handler
            if command.type in self._handlers:
                await self._handlers[command.type](command)
            else:
                # Default handlers
                await self._apply_default(command)
            
            logger.debug(
                f"Applied entry {entry.index} "
                f"(term={entry.term}, type={command.type.value})"
            )
            
        except Exception as e:
            logger.error(f"Error applying entry {entry.index}: {e}")
    
    async def _apply_default(self, command: Command):
        """
        Apply a command using default handlers.
        
        Args:
            command: Command to apply
        """
        cmd_type = command.type
        data = command.data
        
        if cmd_type == CommandType.ADD_NODE:
            node_id = data.get("node_id")
            if node_id:
                self._nodes[node_id] = data
        
        elif cmd_type == CommandType.REMOVE_NODE:
            node_id = data.get("node_id")
            if node_id:
                self._nodes.pop(node_id, None)
        
        elif cmd_type == CommandType.UPDATE_NODE:
            node_id = data.get("node_id")
            if node_id and node_id in self._nodes:
                self._nodes[node_id].update(data)
        
        elif cmd_type == CommandType.CREATE_USER:
            user_id = data.get("user_id") or data.get("id")
            if user_id:
                self._users[user_id] = data
        
        elif cmd_type == CommandType.UPDATE_USER:
            user_id = data.get("user_id") or data.get("id")
            if user_id and user_id in self._users:
                self._users[user_id].update(data)
        
        elif cmd_type == CommandType.DELETE_USER:
            user_id = data.get("user_id") or data.get("id")
            if user_id:
                self._users.pop(user_id, None)
        
        elif cmd_type == CommandType.REGISTER_DOCUMENT:
            doc_id = data.get("document_id") or data.get("id")
            if doc_id:
                self._documents[doc_id] = data
        
        elif cmd_type == CommandType.UNREGISTER_DOCUMENT:
            doc_id = data.get("document_id") or data.get("id")
            if doc_id:
                self._documents.pop(doc_id, None)
        
        elif cmd_type == CommandType.ASSIGN_PARTITION:
            partition_id = data.get("partition_id")
            if partition_id:
                self._partitions[partition_id] = data
        
        elif cmd_type == CommandType.MOVE_PARTITION:
            partition_id = data.get("partition_id")
            if partition_id and partition_id in self._partitions:
                self._partitions[partition_id].update(data)
        
        elif cmd_type == CommandType.UPDATE_CONFIG:
            self._config.update(data)
        
        elif cmd_type == CommandType.NOOP:
            pass  # No-op, just for commitment
    
    def register_handler(
        self,
        command_type: CommandType,
        handler: CommandHandler,
    ):
        """
        Register a custom handler for a command type.
        
        Args:
            command_type: Type of command
            handler: Async function to handle the command
        """
        self._handlers[command_type] = handler
    
    def get_status(self) -> Dict[str, Any]:
        """Get state machine status."""
        return {
            "last_applied": self._last_applied,
            "nodes_count": len(self._nodes),
            "users_count": len(self._users),
            "documents_count": len(self._documents),
            "partitions_count": len(self._partitions),
            "running": self._running,
        }
    
    def get_full_state(self) -> Dict[str, Any]:
        """Get full state machine state."""
        return {
            "last_applied": self._last_applied,
            "nodes": dict(self._nodes),
            "users": dict(self._users),
            "documents": dict(self._documents),
            "partitions": dict(self._partitions),
            "config": dict(self._config),
        }
    
    def get_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get all nodes."""
        return dict(self._nodes)
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific node."""
        return self._nodes.get(node_id)
    
    def get_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all users."""
        return dict(self._users)
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific user."""
        return self._users.get(user_id)
    
    def get_documents(self) -> Dict[str, Dict[str, Any]]:
        """Get all documents."""
        return dict(self._documents)
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document."""
        return self._documents.get(doc_id)
    
    def get_document_replicas(self, doc_id: str) -> List[str]:
        """Get replica node IDs for a document."""
        doc = self._documents.get(doc_id)
        if doc:
            return doc.get("replicas", [])
        return []
    
    def get_partitions(self) -> Dict[str, Dict[str, Any]]:
        """Get all partitions."""
        return dict(self._partitions)
    
    def get_partition(self, partition_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific partition."""
        return self._partitions.get(partition_id)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration."""
        return dict(self._config)

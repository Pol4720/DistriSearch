"""
Persistent State Machine for Raft with SQLite backing.

This is the AP-mode state machine that persists all state to SQLite,
ensuring that state survives restarts and can be replicated across nodes.

Key differences from in-memory StateMachine:
- All state changes are persisted to SQLite
- State can be recovered after node restart
- Supports user operations (create, update, delete)
- Integrates with UserDocumentRegistry for eventual consistency
"""

import asyncio
import logging
import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable, List
from datetime import datetime, timezone

from .raft_state import RaftState
from .log_entry import LogStore, LogEntry
from ...storage.sqlite_client import SQLiteClient
from ...storage.sqlite_user_repository import SQLiteUserRepository
from ...storage.sqlite_cluster_repository import (
    SQLiteNodeRepository,
    SQLitePartitionRepository,
)
from ...storage.user_document_registry import UserDocumentRegistry
from ...storage.models import UserModel, NodeModel, PartitionModel

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands that can be applied to state machine."""
    
    # Cluster membership
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_NODE = "update_node"
    
    # User operations (persisted in SQLite)
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    
    # Document registry operations (Gossip-based, but replicated for consistency)
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


class PersistentStateMachine:
    """
    Persistent state machine for DistriSearch AP mode.
    
    Uses SQLite for durable storage of:
    - Users (credentials, profiles)
    - Nodes (cluster membership)
    - Partitions (VP-Tree partitions)
    - Configuration
    
    Uses UserDocumentRegistry for:
    - User -> Document mappings (eventually consistent via Gossip)
    """
    
    def __init__(
        self,
        state: RaftState,
        log_store: LogStore,
        sqlite_client: SQLiteClient,
        document_registry: Optional[UserDocumentRegistry] = None,
    ):
        """
        Initialize persistent state machine.
        
        Args:
            state: Raft state manager
            log_store: Log entry storage
            sqlite_client: SQLite client for persistent storage
            document_registry: Optional document registry for Gossip
        """
        self.state = state
        self.log_store = log_store
        self.sqlite = sqlite_client
        self.document_registry = document_registry
        
        # Repositories (created after schema initialization)
        self.user_repo: Optional[SQLiteUserRepository] = None
        self.node_repo: Optional[SQLiteNodeRepository] = None
        self.partition_repo: Optional[SQLitePartitionRepository] = None
        
        # Command handlers by type
        self._handlers: Dict[CommandType, CommandHandler] = {}
        
        # In-memory cache for frequently accessed state
        self._config_cache: Dict[str, Any] = {}
        
        # Applied request IDs (for deduplication)
        self._applied_requests: Dict[str, Any] = {}
        self._max_applied_requests = 10000
        
        # Background apply task
        self._apply_task: Optional[asyncio.Task] = None
        self._apply_event = asyncio.Event()
        
        # Lock for state modifications
        self._lock = asyncio.Lock()
        
        # Initialized flag
        self._initialized = False
        
        # Register default handlers
        self._register_default_handlers()
        
        logger.info(f"PersistentStateMachine initialized for node {state.node_id}")
    
    async def initialize(self):
        """Initialize SQLite schema and repositories."""
        if self._initialized:
            return
        
        # Initialize SQLite schema
        await self.sqlite.initialize_schema()
        
        # Create repositories
        self.user_repo = SQLiteUserRepository(self.sqlite)
        self.node_repo = SQLiteNodeRepository(self.sqlite)
        self.partition_repo = SQLitePartitionRepository(self.sqlite)
        
        # Load config cache
        await self._load_config_cache()
        
        # Load applied requests from persistent storage
        await self._load_applied_requests()
        
        self._initialized = True
        logger.info("PersistentStateMachine initialized with SQLite")
    
    async def _load_config_cache(self):
        """Load configuration from SQLite into cache."""
        try:
            rows = await self.sqlite.fetch_all(
                "SELECT key, value FROM config"
            )
            for row in rows:
                try:
                    self._config_cache[row[0]] = json.loads(row[1])
                except json.JSONDecodeError:
                    self._config_cache[row[0]] = row[1]
        except Exception as e:
            # Config table might not exist yet
            logger.debug(f"Could not load config cache: {e}")
    
    async def _load_applied_requests(self):
        """Load applied request IDs from persistent storage."""
        try:
            rows = await self.sqlite.fetch_all(
                """
                SELECT request_id, result FROM applied_requests
                ORDER BY applied_at DESC
                LIMIT ?
                """,
                (self._max_applied_requests,)
            )
            for row in rows:
                try:
                    self._applied_requests[row[0]] = json.loads(row[1])
                except json.JSONDecodeError:
                    self._applied_requests[row[0]] = row[1]
        except Exception as e:
            # Table might not exist yet
            logger.debug(f"Could not load applied requests: {e}")
    
    async def _persist_applied_request(self, request_id: str, result: Any):
        """Persist an applied request ID for deduplication."""
        try:
            await self.sqlite.execute(
                """
                INSERT OR REPLACE INTO applied_requests (request_id, result, applied_at)
                VALUES (?, ?, ?)
                """,
                (request_id, json.dumps(result), datetime.now(timezone.utc).isoformat())
            )
        except Exception as e:
            logger.debug(f"Could not persist applied request: {e}")
    
    def _register_default_handlers(self):
        """Register default command handlers."""
        # Cluster operations
        self._handlers[CommandType.ADD_NODE] = self._handle_add_node
        self._handlers[CommandType.REMOVE_NODE] = self._handle_remove_node
        self._handlers[CommandType.UPDATE_NODE] = self._handle_update_node
        
        # User operations
        self._handlers[CommandType.CREATE_USER] = self._handle_create_user
        self._handlers[CommandType.UPDATE_USER] = self._handle_update_user
        self._handlers[CommandType.DELETE_USER] = self._handle_delete_user
        
        # Document registry operations
        self._handlers[CommandType.REGISTER_DOCUMENT] = self._handle_register_document
        self._handlers[CommandType.UNREGISTER_DOCUMENT] = self._handle_unregister_document
        
        # Partition operations
        self._handlers[CommandType.ASSIGN_PARTITION] = self._handle_assign_partition
        self._handlers[CommandType.MOVE_PARTITION] = self._handle_move_partition
        
        # Configuration
        self._handlers[CommandType.UPDATE_CONFIG] = self._handle_update_config
        
        # No-op
        self._handlers[CommandType.NOOP] = self._handle_noop
    
    def register_handler(
        self,
        command_type: CommandType,
        handler: CommandHandler,
    ):
        """Register a custom command handler."""
        self._handlers[command_type] = handler
    
    async def start(self):
        """Start the state machine apply loop."""
        if not self._initialized:
            await self.initialize()
        
        if self._apply_task and not self._apply_task.done():
            return
        
        self._apply_task = asyncio.create_task(self._apply_loop())
        logger.info("Persistent state machine apply loop started")
    
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
        """Background loop that applies committed entries."""
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        self._apply_event.wait(),
                        timeout=0.1,
                    )
                    self._apply_event.clear()
                except asyncio.TimeoutError:
                    pass
                
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
        """Apply a single log entry to the state machine."""
        try:
            command = Command.from_dict(entry.command)
            
            # Check for duplicate request
            if command.request_id:
                if command.request_id in self._applied_requests:
                    logger.debug(f"Skipping duplicate request {command.request_id}")
                    return
            
            # Find handler
            handler = self._handlers.get(command.type)
            if handler is None:
                logger.warning(f"No handler for command type {command.type}")
                return
            
            # Apply command (persisted to SQLite)
            async with self._lock:
                result = await handler(command)
            
            # Record applied request
            if command.request_id:
                self._applied_requests[command.request_id] = result
                await self._persist_applied_request(command.request_id, result)
                
                # Prune old requests from memory
                if len(self._applied_requests) > self._max_applied_requests:
                    oldest = list(self._applied_requests.keys())[
                        :len(self._applied_requests) - self._max_applied_requests
                    ]
                    for key in oldest:
                        del self._applied_requests[key]
            
            logger.debug(f"Applied entry {entry.index}: {command.type.value}")
            
        except Exception as e:
            logger.error(f"Error applying entry {entry.index}: {e}")
            raise  # Re-raise to stop apply loop on critical errors
    
    # ==================== Node Handlers ====================
    
    async def _handle_add_node(self, command: Command) -> Any:
        """Handle ADD_NODE command - persist to SQLite."""
        node_id = command.data.get("node_id")
        node_info = command.data.get("node_info", {})
        
        if not node_id:
            return {"success": False, "error": "Missing node_id"}
        
        # Create node model
        node = NodeModel(
            node_id=node_id,
            address=node_info.get("address", ""),
            role=node_info.get("role", "slave"),
            status="active",
            last_heartbeat=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        # Persist to SQLite
        await self.node_repo.create(node)
        
        # Update Raft cluster membership
        address = node_info.get("address")
        if address:
            await self.state.add_cluster_node(node_id, address)
        
        logger.info(f"Added node {node_id} to cluster (SQLite)")
        return {"success": True, "node_id": node_id}
    
    async def _handle_remove_node(self, command: Command) -> Any:
        """Handle REMOVE_NODE command - remove from SQLite."""
        node_id = command.data.get("node_id")
        
        if not node_id:
            return {"success": False, "error": "Missing node_id"}
        
        # Remove from SQLite
        await self.node_repo.delete(node_id)
        
        # Remove from Raft cluster
        await self.state.remove_cluster_node(node_id)
        
        logger.info(f"Removed node {node_id} from cluster (SQLite)")
        return {"success": True, "node_id": node_id}
    
    async def _handle_update_node(self, command: Command) -> Any:
        """Handle UPDATE_NODE command - update in SQLite."""
        node_id = command.data.get("node_id")
        updates = command.data.get("updates", {})
        
        if not node_id:
            return {"success": False, "error": "Missing node_id"}
        
        # Get existing node
        existing = await self.node_repo.find_by_id(node_id)
        if not existing:
            return {"success": False, "error": "Node not found"}
        
        # Apply updates
        node_dict = existing.to_dict()
        node_dict.update(updates)
        node_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        updated_node = NodeModel.from_dict(node_dict)
        await self.node_repo.update(node_id, updated_node)
        
        logger.info(f"Updated node {node_id} (SQLite): {updates}")
        return {"success": True, "node_id": node_id}
    
    # ==================== User Handlers ====================
    
    async def _handle_create_user(self, command: Command) -> Any:
        """Handle CREATE_USER command - persist to SQLite."""
        user_data = command.data.get("user", {})
        
        if not user_data:
            return {"success": False, "error": "Missing user data"}
        
        # Create user model
        user = UserModel.from_dict(user_data)
        
        # Persist to SQLite
        user_id = await self.user_repo.create(user)
        
        logger.info(f"Created user {user.username} (SQLite)")
        return {"success": True, "user_id": user_id}
    
    async def _handle_update_user(self, command: Command) -> Any:
        """Handle UPDATE_USER command - update in SQLite."""
        user_id = command.data.get("user_id")
        updates = command.data.get("updates", {})
        
        if not user_id:
            return {"success": False, "error": "Missing user_id"}
        
        # Get existing user
        existing = await self.user_repo.find_by_id(user_id)
        if not existing:
            return {"success": False, "error": "User not found"}
        
        # Apply updates
        user_dict = existing.to_dict()
        user_dict.update(updates)
        user_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        updated_user = UserModel.from_dict(user_dict)
        await self.user_repo.update(user_id, updated_user)
        
        logger.info(f"Updated user {user_id} (SQLite)")
        return {"success": True, "user_id": user_id}
    
    async def _handle_delete_user(self, command: Command) -> Any:
        """Handle DELETE_USER command - remove from SQLite."""
        user_id = command.data.get("user_id")
        
        if not user_id:
            return {"success": False, "error": "Missing user_id"}
        
        # Remove user from SQLite
        await self.user_repo.delete(user_id)
        
        # Note: Documents owned by user remain in local MongoDB instances
        # The UserDocumentRegistry will handle orphaned document cleanup
        
        logger.info(f"Deleted user {user_id} (SQLite)")
        return {"success": True, "user_id": user_id}
    
    # ==================== Document Registry Handlers ====================
    
    async def _handle_register_document(self, command: Command) -> Any:
        """Handle REGISTER_DOCUMENT command - update registry."""
        user_id = command.data.get("user_id")
        doc_id = command.data.get("doc_id")
        node_id = command.data.get("node_id")
        metadata = command.data.get("metadata", {})
        
        if not all([user_id, doc_id, node_id]):
            return {"success": False, "error": "Missing required fields"}
        
        # Register in document registry (Gossip-based)
        if self.document_registry:
            self.document_registry.register_document(
                user_id=user_id,
                doc_id=doc_id,
                node_id=node_id,
                metadata=metadata,
            )
        
        logger.debug(f"Registered document {doc_id} for user {user_id} on node {node_id}")
        return {"success": True, "doc_id": doc_id}
    
    async def _handle_unregister_document(self, command: Command) -> Any:
        """Handle UNREGISTER_DOCUMENT command - update registry."""
        user_id = command.data.get("user_id")
        doc_id = command.data.get("doc_id")
        
        if not all([user_id, doc_id]):
            return {"success": False, "error": "Missing required fields"}
        
        # Unregister from document registry
        if self.document_registry:
            self.document_registry.unregister_document(user_id=user_id, doc_id=doc_id)
        
        logger.debug(f"Unregistered document {doc_id} for user {user_id}")
        return {"success": True, "doc_id": doc_id}
    
    # ==================== Partition Handlers ====================
    
    async def _handle_assign_partition(self, command: Command) -> Any:
        """Handle ASSIGN_PARTITION command - persist to SQLite."""
        partition_id = command.data.get("partition_id")
        node_id = command.data.get("node_id")
        centroid = command.data.get("centroid", [])
        doc_ids = command.data.get("doc_ids", [])
        
        if not partition_id:
            return {"success": False, "error": "Missing partition_id"}
        
        # Create partition model
        partition = PartitionModel(
            partition_id=partition_id,
            node_id=node_id,
            centroid=centroid,
            doc_count=len(doc_ids),
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        # Persist to SQLite
        await self.partition_repo.create(partition)
        
        logger.info(f"Assigned partition {partition_id} to node {node_id} (SQLite)")
        return {"success": True, "partition_id": partition_id}
    
    async def _handle_move_partition(self, command: Command) -> Any:
        """Handle MOVE_PARTITION command - update in SQLite."""
        partition_id = command.data.get("partition_id")
        to_node = command.data.get("to_node")
        
        if not partition_id:
            return {"success": False, "error": "Missing partition_id"}
        
        # Get existing partition
        existing = await self.partition_repo.find_by_id(partition_id)
        if not existing:
            return {"success": False, "error": "Partition not found"}
        
        # Update node assignment
        existing.node_id = to_node
        existing.updated_at = datetime.now(timezone.utc)
        
        await self.partition_repo.update(partition_id, existing)
        
        logger.info(f"Moved partition {partition_id} to node {to_node} (SQLite)")
        return {"success": True, "partition_id": partition_id}
    
    # ==================== Config Handler ====================
    
    async def _handle_update_config(self, command: Command) -> Any:
        """Handle UPDATE_CONFIG command - persist to SQLite."""
        key = command.data.get("key")
        value = command.data.get("value")
        
        if not key:
            return {"success": False, "error": "Missing key"}
        
        # Persist to SQLite
        await self.sqlite.execute(
            """
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(value), datetime.now(timezone.utc).isoformat())
        )
        
        # Update cache
        self._config_cache[key] = value
        
        logger.info(f"Updated config {key} = {value} (SQLite)")
        return {"success": True, "key": key}
    
    async def _handle_noop(self, command: Command) -> Any:
        """Handle NOOP command (used for leader commitment)."""
        return {"success": True}
    
    # ==================== State Access Methods ====================
    
    async def get_node(self, node_id: str) -> Optional[NodeModel]:
        """Get node information from SQLite."""
        return await self.node_repo.find_by_id(node_id)
    
    async def get_all_nodes(self) -> List[NodeModel]:
        """Get all nodes from SQLite."""
        return await self.node_repo.find_all()
    
    async def get_active_nodes(self) -> List[NodeModel]:
        """Get all active nodes from SQLite."""
        return await self.node_repo.find_active()
    
    async def get_user(self, user_id: str) -> Optional[UserModel]:
        """Get user by ID from SQLite."""
        return await self.user_repo.find_by_id(user_id)
    
    async def get_user_by_username(self, username: str) -> Optional[UserModel]:
        """Get user by username from SQLite."""
        return await self.user_repo.find_by_username(username)
    
    async def get_partition(self, partition_id: str) -> Optional[PartitionModel]:
        """Get partition information from SQLite."""
        return await self.partition_repo.find_by_id(partition_id)
    
    async def get_partitions_for_node(self, node_id: str) -> List[PartitionModel]:
        """Get all partitions assigned to a node."""
        return await self.partition_repo.find_by_node(node_id)
    
    def get_user_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Get documents for a user from the registry."""
        if self.document_registry:
            return self.document_registry.get_user_documents(user_id)
        return []
    
    def get_document_location(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document location from the registry."""
        if self.document_registry:
            return self.document_registry.get_document_location(doc_id)
        return None
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value from cache."""
        return self._config_cache.get(key, default)
    
    async def get_full_state(self) -> Dict[str, Any]:
        """Get complete cluster state summary."""
        nodes = await self.node_repo.find_all()
        partitions = await self.partition_repo.find_all()
        
        return {
            "nodes": [n.to_dict() for n in nodes],
            "nodes_count": len(nodes),
            "partitions_count": len(partitions),
            "config": self._config_cache.copy(),
            "document_registry_size": (
                len(self.document_registry._documents) if self.document_registry else 0
            ),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get state machine status for monitoring."""
        return {
            "last_applied": self.state.volatile.last_applied,
            "commit_index": self.state.volatile.commit_index,
            "initialized": self._initialized,
            "apply_loop_active": (
                self._apply_task is not None and
                not self._apply_task.done()
            ),
            "persistent": True,
            "storage": "sqlite",
        }
    
    # ==================== Snapshot Support ====================
    
    async def create_snapshot(self) -> Dict[str, Any]:
        """
        Create a snapshot of the current state for Raft log compaction.
        
        Returns:
            Dictionary containing all state that needs to be replicated
        """
        nodes = await self.node_repo.find_all()
        partitions = await self.partition_repo.find_all()
        
        # Get all users (for full state replication)
        users = await self.sqlite.fetch_all(
            "SELECT * FROM users ORDER BY id"
        )
        
        return {
            "nodes": [n.to_dict() for n in nodes],
            "partitions": [p.to_dict() for p in partitions],
            "users": [dict(row) for row in users],
            "config": self._config_cache.copy(),
            "document_registry": (
                self.document_registry.get_state_for_gossip()
                if self.document_registry else {}
            ),
            "last_included_index": self.state.volatile.last_applied,
            "last_included_term": self.state.persistent.current_term,
        }
    
    async def restore_snapshot(self, snapshot: Dict[str, Any]):
        """
        Restore state from a snapshot.
        
        Args:
            snapshot: Snapshot data from create_snapshot
        """
        async with self._lock:
            # Clear existing data
            await self.sqlite.execute("DELETE FROM nodes")
            await self.sqlite.execute("DELETE FROM partitions")
            await self.sqlite.execute("DELETE FROM users")
            await self.sqlite.execute("DELETE FROM config")
            
            # Restore nodes
            for node_data in snapshot.get("nodes", []):
                node = NodeModel.from_dict(node_data)
                await self.node_repo.create(node)
            
            # Restore partitions
            for partition_data in snapshot.get("partitions", []):
                partition = PartitionModel.from_dict(partition_data)
                await self.partition_repo.create(partition)
            
            # Restore users
            for user_data in snapshot.get("users", []):
                user = UserModel.from_dict(user_data)
                await self.user_repo.create(user)
            
            # Restore config
            for key, value in snapshot.get("config", {}).items():
                await self.sqlite.execute(
                    """
                    INSERT OR REPLACE INTO config (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, json.dumps(value), datetime.now(timezone.utc).isoformat())
                )
                self._config_cache[key] = value
            
            # Restore document registry
            if self.document_registry and "document_registry" in snapshot:
                self.document_registry.merge_remote_state(
                    snapshot["document_registry"],
                    "snapshot_restore"
                )
            
            logger.info("Restored state from snapshot")

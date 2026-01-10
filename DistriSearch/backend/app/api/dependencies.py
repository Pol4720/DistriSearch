"""
Dependencies Module
FastAPI dependency injection for DistriSearch

Architecture:
- Users, nodes, partitions are stored in SQLite (replicated via Raft)
- Documents are stored in local MongoDB (each node has its own)
- Document registry uses Gossip protocol for eventual consistency
"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from pathlib import Path
import os
import logging
import aiohttp
import asyncio

# Storage imports
from ..storage.sqlite_client import SQLiteClient
from ..storage.sqlite_user_repository import SQLiteUserRepository
from ..storage.sqlite_cluster_repository import (
    SQLiteNodeRepository,
    SQLitePartitionRepository,
)
from ..storage.user_document_registry import UserDocumentRegistry
from ..storage.mongodb import MongoDBClient, DocumentRepository

# Distributed imports
# NOTE: Raft is DISABLED - using Bully election instead
# from ..distributed.consensus import (
#     RaftNode,
#     PersistentStateMachine,
# )
from ..distributed.consensus.bully_election import BullyElection
from ..distributed.communication import HeartbeatService, MessageBroker
from ..distributed.coordination import ClusterManager
from ..distributed.coordination.cluster_manager import NodeRole
from ..core.search import SearchEngine
from ..config import Settings

logger = logging.getLogger(__name__)


# =============================================================================
# Global Instances
# =============================================================================

# SQLite (replicated via Raft)
_sqlite_client: Optional[SQLiteClient] = None
_sqlite_user_repository: Optional[SQLiteUserRepository] = None
_sqlite_node_repository: Optional[SQLiteNodeRepository] = None
_sqlite_partition_repository: Optional[SQLitePartitionRepository] = None

# Document Registry (Gossip-based)
_document_registry: Optional[UserDocumentRegistry] = None

# MongoDB (local per node, documents only)
_local_mongodb_client: Optional[MongoDBClient] = None
_local_document_repository: Optional[DocumentRepository] = None
_search_history_repository: Optional[Any] = None
_node_repository: Optional[Any] = None
_cluster_repository: Optional[Any] = None

# Distributed services
# NOTE: Raft is DISABLED - using Bully election for leader election
# _raft_node: Optional[RaftNode] = None
# _persistent_state_machine: Optional[PersistentStateMachine] = None
_bully_election: Optional[BullyElection] = None
_bully_peers: Dict[str, str] = {}  # Peer ID -> address mapping
_heartbeat_service: Optional[HeartbeatService] = None
_message_broker: Optional[MessageBroker] = None
_cluster_manager: Optional[ClusterManager] = None
_search_engine: Optional[SearchEngine] = None
_settings: Optional[Settings] = None


# =============================================================================
# Settings
# =============================================================================

def get_settings() -> Settings:
    """Get application settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_cluster_peers() -> Dict[str, str]:
    """Get all known cluster peers (node_id -> address)."""
    return _bully_peers.copy()


def get_node_id() -> Optional[str]:
    """Get current node ID."""
    if _settings:
        return _settings.node_id
    return None



# =============================================================================
# RPC Sender for Raft - DISABLED
# =============================================================================
# NOTE: Raft is disabled. This function is kept for reference but not used.
# async def _create_rpc_sender(settings: Settings):
#     """Create an RPC sender function for Raft communication."""
#     ...


# =============================================================================
# Message Sender for Bully Election
# =============================================================================

async def _create_bully_sender(settings: Settings):
    """Create a message sender function for Bully election."""
    async def send_message(target_address: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send Bully message to target node."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{target_address}/api/v1/internal/bully"
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            logger.debug(f"Bully message to {target_address} failed: {e}")
            return None
    return send_message


# =============================================================================
# Initialization
# =============================================================================

async def init_dependencies(settings: Settings):
    """
    Initialize all dependencies at application startup.
    
    Architecture:
    - SQLite stores users, nodes, partitions (replicated via Raft)
    - Local MongoDB stores documents (each node has its own)
    - UserDocumentRegistry tracks user->documents (Gossip-based)
    """
    global _sqlite_client, _sqlite_user_repository, _sqlite_node_repository
    global _sqlite_partition_repository, _document_registry
    global _local_mongodb_client, _local_document_repository
    # NOTE: Raft disabled - using Bully election
    global _heartbeat_service, _message_broker, _cluster_manager
    global _search_engine, _settings, _search_history_repository
    
    _settings = settings
    node_id = settings.node_id
    
    logger.info(f"Initializing dependencies for node {node_id}")
    
    # =========================================================================
    # 1. Initialize SQLite (replicated via Raft)
    # =========================================================================
    sqlite_path = Path(settings.data_dir) / "sqlite" / f"{node_id}.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    
    _sqlite_client = SQLiteClient(db_path=str(sqlite_path))
    await _sqlite_client.connect()  # connect() already initializes schema
    
    # Create SQLite repositories
    _sqlite_user_repository = SQLiteUserRepository(_sqlite_client)
    _sqlite_node_repository = SQLiteNodeRepository(_sqlite_client)
    _sqlite_partition_repository = SQLitePartitionRepository(_sqlite_client)
    
    logger.info(f"SQLite initialized at {sqlite_path}")
    
    # =========================================================================
    # 2. Initialize Document Registry (Gossip-based)
    # =========================================================================
    _document_registry = UserDocumentRegistry(client=_sqlite_client, node_id=node_id)
    
    # Note: peers will be set after Bully election is configured
    logger.info("UserDocumentRegistry initialized for Gossip protocol")
    
    # =========================================================================
    # 3. Initialize Local MongoDB (documents only - SLAVES ONLY)
    # =========================================================================
    # Master does NOT use MongoDB - it only coordinates via SQLite + Redis
    # Each slave node has its OWN MongoDB instance for document storage
    
    if settings.is_master:
        logger.info("Master node: Skipping MongoDB initialization (no document storage)")
        _local_mongodb_client = None
        _local_document_repository = None
        _search_history_repository = None
    else:
        # Slave node: Initialize local MongoDB
        local_mongo_uri = settings.local_mongodb_uri or settings.mongodb_uri
        local_mongo_db = f"distrisearch_{node_id}"
        
        _local_mongodb_client = MongoDBClient(
            uri=local_mongo_uri,
            database_name=local_mongo_db
        )
        await _local_mongodb_client.connect()
        
        _local_document_repository = DocumentRepository(_local_mongodb_client)
        await _local_document_repository.ensure_indexes()
        
        # Initialize Search History Repository
        from ..storage.mongodb import SearchHistoryRepository
        _search_history_repository = SearchHistoryRepository(_local_mongodb_client)
        await _search_history_repository.ensure_indexes()
        
        logger.info(f"Local MongoDB initialized: {local_mongo_db}")
    
    # =========================================================================
    # 4. RAFT DISABLED - Using Bully Election for leader election
    # =========================================================================
    # Raft was causing issues with persistent state machine loops.
    # Bully election is simpler and works better for our use case.
    
    node_address = f"{settings.node_address}:{settings.api_port}"
    
    logger.info("Raft DISABLED - using Bully election for leader election")
    
    # =========================================================================
    # 4.5. Get peers from configuration (used by Bully)
    # =========================================================================
    raft_peers = settings.raft_peers_list
    # Peers are extracted from raft_peers config but used for Bully election
    
    # =========================================================================
    # 4.6. Initialize Bully Election (simpler leader election)
    # =========================================================================
    global _bully_election, _bully_peers
    
    bully_peers: Dict[str, str] = {}
    if raft_peers:
        for peer_address in raft_peers:
            peer_host = peer_address.split(":")[0]
            if peer_host.startswith("distrisearch-"):
                peer_id = peer_host.replace("distrisearch-", "")
            else:
                peer_id = peer_host
            
            if peer_id != node_id:
                bully_peers[peer_id] = peer_address
    
    # Store globally for access by other modules
    _bully_peers = bully_peers.copy()
    
    bully_sender = await _create_bully_sender(settings)
    
    async def on_become_leader():
        """Callback when this node becomes the Bully leader."""
        logger.info(f"Node {node_id} is now the BULLY LEADER")
        # Update cluster manager with all known peers
        if _cluster_manager:
            await _cluster_manager.handle_leader_elected(node_id, bully_peers)
    
    async def on_leader_change(new_leader_id: str):
        """Callback when leader changes."""
        logger.info(f"New Bully leader: {new_leader_id}")
        if _cluster_manager:
            # Pass peers so the new leader can register them
            await _cluster_manager.handle_leader_elected(new_leader_id, bully_peers if new_leader_id == node_id else None)
    
    _bully_election = BullyElection(
        node_id=node_id,
        peers=bully_peers,
        send_message=bully_sender,
        on_become_leader=on_become_leader,
        on_leader_change=on_leader_change,
        election_timeout=10.0,  # 10 seconds timeout
        heartbeat_interval=3.0,  # 3 seconds heartbeat
    )
    
    # Start Bully election
    await _bully_election.start()
    logger.info(f"Bully Election initialized with {len(bully_peers)} peers")
    
    # =========================================================================
    # 5. Initialize Distributed Services
    # =========================================================================
    node_role = NodeRole.MASTER if settings.is_master else NodeRole.SLAVE
    
    # HeartbeatService
    _heartbeat_service = HeartbeatService(
        heartbeat_interval=settings.heartbeat_interval,
        suspect_threshold=settings.heartbeat_timeout,
        dead_threshold=settings.heartbeat_timeout * settings.max_heartbeat_failures,
    )
    
    # MessageBroker
    _message_broker = MessageBroker(node_id=node_id)
    
    # ClusterManager
    _cluster_manager = ClusterManager(
        node_id=node_id,
        address=node_address,
        role=node_role,
        raft_node=None,  # Raft disabled - using Bully election
        heartbeat_service=_heartbeat_service,
        message_broker=_message_broker,
        min_healthy_nodes=1,
    )
    _cluster_manager.cluster_id = settings.cluster_id
    _cluster_manager.replication_factor = settings.replication_factor
    
    await _cluster_manager.start()
    
    logger.info(f"ClusterManager started for node {node_id} as {node_role.value}")
    
    # =========================================================================
    # 5.1. Sync ClusterManager with Bully election state
    # =========================================================================
    # Bully may have elected a leader before ClusterManager was ready
    if _bully_election and _bully_election.is_leader:
        logger.info("Syncing ClusterManager with Bully leader state")
        await _cluster_manager.handle_leader_elected(node_id, _bully_peers)
    elif _bully_election and _bully_election.leader_id:
        logger.info(f"Syncing ClusterManager: leader is {_bully_election.leader_id}")
        await _cluster_manager.handle_leader_elected(_bully_election.leader_id, None)
    
    # =========================================================================
    # 5.2. Start UserDocumentRegistry with peers for Gossip
    # =========================================================================
    if _document_registry:
        peer_addresses = list(_bully_peers.values())
        _document_registry.set_peers(peer_addresses)
        await _document_registry.start()
        logger.info(f"UserDocumentRegistry started with {len(peer_addresses)} peers for gossip")
    
    # =========================================================================
    # 6. Initialize Search Engine
    # =========================================================================
    _search_engine = SearchEngine()
    
    # =========================================================================
    # 7. Set up Auth with SQLite User Repository
    # =========================================================================
    from .auth import set_sqlite_user_repository
    set_sqlite_user_repository(_sqlite_user_repository)
    
    # =========================================================================
    # 8. Initial User Sync from Peers
    # =========================================================================
    # Schedule a background task to sync users from peers after a delay
    # This ensures we have all users from other nodes when we start
    asyncio.create_task(_sync_users_from_peers_delayed(bully_peers, 10.0))
    
    # =========================================================================
    # 9. Schedule periodic full sync for consistency
    # =========================================================================
    asyncio.create_task(_periodic_full_sync(bully_peers, interval=60.0))
    
    logger.info("Dependencies initialized successfully")


async def _sync_users_from_peers_delayed(peers: Dict[str, str], delay: float):
    """
    Sync users from peer nodes after a delay.
    
    This runs as a background task after initialization to populate
    local user database with users from other nodes.
    """
    await asyncio.sleep(delay)
    
    if not peers:
        logger.debug("No peers to sync users from")
        return
    
    logger.info(f"Starting initial user sync from {len(peers)} peers")
    
    for peer_id, peer_address in peers.items():
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{peer_address}/api/v1/internal/sync/users"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok":
                            users = data.get("users", [])
                            logger.info(f"Got {len(users)} users from {peer_id}")
                            
                            # Sync each user locally
                            for user_data in users:
                                await _sync_single_user(user_data)
                    else:
                        logger.warning(f"Failed to get users from {peer_id}: status {resp.status}")
        except Exception as e:
            logger.warning(f"Error syncing users from {peer_id}: {e}")


async def _sync_single_user(user_data: Dict[str, Any]) -> None:
    """Sync a single user to local database."""
    from .auth import get_user_repository
    from ..storage.models import UserModel, UserStatus
    
    try:
        user_repo = await get_user_repository()
        
        # Check if already exists
        existing = await user_repo.find_by_email(user_data.get("email", ""))
        if existing:
            return
        
        existing = await user_repo.find_by_username(user_data.get("username", ""))
        if existing:
            return
        
        # Create user
        user = UserModel(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            password_hash=user_data["password_hash"],
            salt=user_data["salt"],
            role=user_data.get("role", "user"),
            status=UserStatus.ACTIVE,
            full_name=user_data.get("full_name"),
        )
        
        await user_repo.create(user)
        logger.info(f"Synced user {user.username} from peer")
        
    except Exception as e:
        logger.debug(f"Could not sync user: {e}")


async def _periodic_full_sync(peers: Dict[str, str], interval: float = 60.0):
    """
    Periodically perform full sync with peers.
    
    This ensures consistency even after network partitions heal.
    """
    await asyncio.sleep(interval)  # Initial delay
    
    while True:
        try:
            # Check if any peers are reachable that weren't before
            # This indicates a network partition may have healed
            for peer_id, peer_address in peers.items():
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://{peer_address}/api/v1/health/live"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                            if resp.status == 200:
                                # Peer is reachable, trigger sync
                                sync_url = f"http://{peer_address}/api/v1/internal/sync/full"
                                async with session.post(sync_url, timeout=aiohttp.ClientTimeout(total=30)) as sync_resp:
                                    if sync_resp.status == 200:
                                        logger.debug(f"Periodic sync with {peer_id} completed")
                except Exception:
                    pass  # Peer not reachable
            
        except Exception as e:
            logger.debug(f"Periodic sync error: {e}")
        
        await asyncio.sleep(interval)


async def shutdown_dependencies():
    """Cleanup dependencies at application shutdown."""
    global _sqlite_client, _local_mongodb_client
    global _cluster_manager, _bully_election
    global _heartbeat_service, _message_broker
    global _document_registry
    
    logger.info("Shutting down dependencies...")
    
    # Stop document registry (gossip loop)
    if _document_registry:
        await _document_registry.stop()
        _document_registry = None
    
    # Stop Bully election
    if _bully_election:
        await _bully_election.stop()
        _bully_election = None
    
    if _cluster_manager:
        await _cluster_manager.shutdown()
        _cluster_manager = None
    
    if _heartbeat_service:
        await _heartbeat_service.stop()
        _heartbeat_service = None
    
    if _message_broker:
        await _message_broker.stop()
        _message_broker = None
    
    if _local_mongodb_client:
        await _local_mongodb_client.disconnect()
        _local_mongodb_client = None
    
    if _sqlite_client:
        await _sqlite_client.disconnect()
        _sqlite_client = None
    
    logger.info("Dependencies cleaned up")


# =============================================================================
# Dependency Getters
# =============================================================================

async def get_sqlite_client() -> SQLiteClient:
    """Get SQLite client instance."""
    if _sqlite_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SQLite client not initialized"
        )
    return _sqlite_client


async def get_user_repository() -> SQLiteUserRepository:
    """Get user repository (SQLite-backed)."""
    if _sqlite_user_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User repository not initialized"
        )
    return _sqlite_user_repository


async def get_node_repository() -> SQLiteNodeRepository:
    """Get node repository (SQLite-backed)."""
    if _sqlite_node_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node repository not initialized"
        )
    return _sqlite_node_repository


async def get_partition_repository() -> SQLitePartitionRepository:
    """Get partition repository (SQLite-backed)."""
    if _sqlite_partition_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Partition repository not initialized"
        )
    return _sqlite_partition_repository


async def get_document_registry() -> UserDocumentRegistry:
    """Get document registry (Gossip-based)."""
    if _document_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document registry not initialized"
        )
    return _document_registry


async def get_local_document_repository() -> DocumentRepository:
    """Get local document repository (MongoDB on this node)."""
    if _local_document_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local document repository not initialized"
        )
    return _local_document_repository


# Alias for backwards compatibility
async def get_document_repository() -> DocumentRepository:
    """Alias for get_local_document_repository."""
    return await get_local_document_repository()


async def get_persistent_state_machine():
    """DEPRECATED: Raft is disabled. PersistentStateMachine not available."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Raft is disabled. PersistentStateMachine not available."
    )


async def get_search_engine() -> SearchEngine:
    """Get search engine instance."""
    if _search_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search engine not initialized"
        )
    return _search_engine


async def get_cluster_manager() -> ClusterManager:
    """Get cluster manager instance."""
    if _cluster_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cluster manager not initialized"
        )
    return _cluster_manager


async def get_raft_node():
    """DEPRECATED: Raft is disabled. Use get_bully_election() instead."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Raft is disabled. Use Bully election instead."
    )


async def get_bully_election() -> BullyElection:
    """Get Bully election instance."""
    if _bully_election is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bully election not initialized"
        )
    return _bully_election


def get_current_node() -> dict:
    """Get current node information."""
    settings = get_settings()
    return {
        "node_id": settings.node_id,
        "address": settings.node_address,
        "port": settings.node_port,
        "role": os.getenv("NODE_ROLE", "slave"),
        "mode": "AP",
    }


# =============================================================================
# Verification Dependencies
# =============================================================================

async def verify_master_node(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """Verify that the current node is the master (Raft leader)."""
    if not cluster_manager.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation can only be performed by the master node"
        )


async def verify_cluster_ready(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """Verify that the cluster is ready."""
    if not cluster_manager.is_initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cluster is not ready"
        )


async def verify_can_authenticate():
    """
    Verify that authentication is possible.
    
    Authentication is ALWAYS possible because:
    - Users are stored in local SQLite (replicated via Raft)
    - Even during network partition, local SQLite has user data
    """
    if _sqlite_user_repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not initialized"
        )
    return True


# =============================================================================
# Rate Limiting (reused from original)
# =============================================================================

class RateLimiter:
    """Simple rate limiter for API endpoints."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict = {}
    
    async def check_rate_limit(self, request: Request):
        """Check if request is within rate limit."""
        import time
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        minute_ago = current_time - 60
        
        if client_ip in self._requests:
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > minute_ago
            ]
        else:
            self._requests[client_ip] = []
        
        if len(self._requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        self._requests[client_ip].append(current_time)


# Global rate limiter instances
search_rate_limiter = RateLimiter(requests_per_minute=60)
upload_rate_limiter = RateLimiter(requests_per_minute=10)


async def rate_limit_search(request: Request):
    """Rate limit for search endpoints."""
    await search_rate_limiter.check_rate_limit(request)


async def rate_limit_upload(request: Request):
    """Rate limit for upload endpoints."""
    await upload_rate_limiter.check_rate_limit(request)


# =============================================================================
# Additional Repository Dependencies
# =============================================================================

async def get_search_history_repository():
    """Get search history repository."""
    global _search_history_repository
    if _search_history_repository is None:
        # Return a mock or None if not initialized
        return None
    return _search_history_repository


async def get_cluster_repository():
    """Get cluster repository."""
    global _cluster_repository
    if _cluster_repository is None:
        return None
    return _cluster_repository


async def get_db():
    """Get database client (MongoDB)."""
    global _local_mongodb_client
    if _local_mongodb_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized"
        )
    return _local_mongodb_client

"""
User Document Registry for DistriSearch.

Distributed registry that tracks which documents belong to which users,
and on which nodes they are stored. This enables AP mode where any node
can answer "what documents does user X have?" even during partitions.

Uses eventual consistency via Gossip-like propagation.
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from dataclasses import dataclass, field

from .sqlite_client import SQLiteClient

logger = logging.getLogger(__name__)


@dataclass
class DocumentRegistryEntry:
    """
    Entry in the user-document registry.
    
    Tracks a single document's ownership and location.
    """
    user_id: str
    document_id: str
    node_id: str
    title: Optional[str] = None
    filename: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_deleted: bool = False
    vector_clock: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "document_id": self.document_id,
            "node_id": self.node_id,
            "title": self.title,
            "filename": self.filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
            "vector_clock": self.vector_clock,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentRegistryEntry":
        """Create from dictionary."""
        def parse_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        
        vector_clock = data.get("vector_clock", {})
        if isinstance(vector_clock, str):
            try:
                vector_clock = json.loads(vector_clock)
            except json.JSONDecodeError:
                vector_clock = {}
        
        return cls(
            user_id=data["user_id"],
            document_id=data["document_id"],
            node_id=data["node_id"],
            title=data.get("title"),
            filename=data.get("filename"),
            created_at=parse_datetime(data.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(data.get("updated_at")) or datetime.now(),
            is_deleted=bool(data.get("is_deleted", False)),
            vector_clock=vector_clock,
        )


class UserDocumentRegistry:
    """
    Distributed registry for user-document mappings.
    
    Features:
    - Persisted to SQLite (replicated via Raft)
    - Gossip-based propagation for eventual consistency
    - Vector clocks for conflict resolution
    - Soft deletes for tombstones
    
    This enables any node to answer queries about user documents
    even during network partitions (AP mode).
    """
    
    TABLE_NAME = "user_document_registry"
    
    def __init__(
        self,
        client: SQLiteClient,
        node_id: str,
        gossip_interval: float = 5.0,
    ):
        """
        Initialize registry.
        
        Args:
            client: SQLite client
            node_id: This node's ID (for vector clock)
            gossip_interval: Seconds between gossip rounds
        """
        self.client = client
        self.node_id = node_id
        self.gossip_interval = gossip_interval
        
        # In-memory cache for fast lookups
        self._cache: Dict[str, Dict[str, DocumentRegistryEntry]] = {}  # user_id -> {doc_id -> entry}
        self._cache_loaded = False
        
        # Gossip state
        self._pending_updates: List[DocumentRegistryEntry] = []
        self._gossip_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks for gossip peers
        self._peer_addresses: List[str] = []
        
        logger.info(f"UserDocumentRegistry initialized for node {node_id}")
    
    async def start(self) -> None:
        """Start the registry and gossip loop."""
        if self._running:
            return
        
        # Load cache from SQLite
        await self._load_cache()
        
        self._running = True
        self._gossip_task = asyncio.create_task(self._gossip_loop())
        
        logger.info("UserDocumentRegistry started")
    
    async def stop(self) -> None:
        """Stop the registry."""
        self._running = False
        
        if self._gossip_task and not self._gossip_task.done():
            self._gossip_task.cancel()
            try:
                await self._gossip_task
            except asyncio.CancelledError:
                pass
        
        logger.info("UserDocumentRegistry stopped")
    
    def set_peers(self, peer_addresses: List[str]) -> None:
        """Set peer node addresses for gossip."""
        self._peer_addresses = peer_addresses
    
    async def register_document(
        self,
        user_id: str,
        document_id: str,
        node_id: str,
        title: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> None:
        """
        Register a document for a user.
        
        Args:
            user_id: Owner user ID
            document_id: Document ID
            node_id: Node where document is stored
            title: Document title
            filename: Original filename
        """
        now = datetime.now()
        
        # Create or update vector clock
        vector_clock = {self.node_id: 1}
        
        # Check if exists and update clock
        existing = await self.get_entry(user_id, document_id)
        if existing:
            vector_clock = existing.vector_clock.copy()
            vector_clock[self.node_id] = vector_clock.get(self.node_id, 0) + 1
        
        entry = DocumentRegistryEntry(
            user_id=user_id,
            document_id=document_id,
            node_id=node_id,
            title=title,
            filename=filename,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            is_deleted=False,
            vector_clock=vector_clock,
        )
        
        # Persist to SQLite
        await self._upsert_entry(entry)
        
        # Update cache
        if user_id not in self._cache:
            self._cache[user_id] = {}
        self._cache[user_id][document_id] = entry
        
        # Queue for gossip
        self._pending_updates.append(entry)
        
        logger.debug(f"Registered document {document_id} for user {user_id}")
    
    async def unregister_document(
        self,
        user_id: str,
        document_id: str,
    ) -> None:
        """
        Unregister (soft delete) a document.
        
        Args:
            user_id: Owner user ID
            document_id: Document ID
        """
        existing = await self.get_entry(user_id, document_id)
        if not existing:
            return
        
        # Update vector clock
        vector_clock = existing.vector_clock.copy()
        vector_clock[self.node_id] = vector_clock.get(self.node_id, 0) + 1
        
        entry = DocumentRegistryEntry(
            user_id=user_id,
            document_id=document_id,
            node_id=existing.node_id,
            title=existing.title,
            filename=existing.filename,
            created_at=existing.created_at,
            updated_at=datetime.now(),
            is_deleted=True,
            vector_clock=vector_clock,
        )
        
        # Persist tombstone
        await self._upsert_entry(entry)
        
        # Update cache
        if user_id in self._cache:
            self._cache[user_id][document_id] = entry
        
        # Queue for gossip
        self._pending_updates.append(entry)
        
        logger.debug(f"Unregistered document {document_id} for user {user_id}")
    
    async def get_user_documents(
        self,
        user_id: str,
        include_deleted: bool = False,
    ) -> List[DocumentRegistryEntry]:
        """
        Get all documents for a user.
        
        Args:
            user_id: User ID
            include_deleted: Include soft-deleted entries
            
        Returns:
            List of document entries
        """
        # Check cache first
        if user_id in self._cache:
            entries = list(self._cache[user_id].values())
            if not include_deleted:
                entries = [e for e in entries if not e.is_deleted]
            return entries
        
        # Fall back to SQLite
        where = "user_id = ?"
        params = [user_id]
        if not include_deleted:
            where += " AND is_deleted = 0"
        
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE {where}",
            tuple(params)
        )
        
        return [DocumentRegistryEntry.from_dict(row) for row in rows]
    
    async def get_entry(
        self,
        user_id: str,
        document_id: str,
    ) -> Optional[DocumentRegistryEntry]:
        """
        Get a specific document entry.
        
        Args:
            user_id: User ID
            document_id: Document ID
            
        Returns:
            Entry or None
        """
        # Check cache
        if user_id in self._cache and document_id in self._cache[user_id]:
            return self._cache[user_id][document_id]
        
        # Fall back to SQLite
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE user_id = ? AND document_id = ?",
            (user_id, document_id)
        )
        
        return DocumentRegistryEntry.from_dict(row) if row else None
    
    async def get_documents_on_node(self, node_id: str) -> List[DocumentRegistryEntry]:
        """
        Get all documents stored on a specific node.
        
        Args:
            node_id: Node ID
            
        Returns:
            List of document entries
        """
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE node_id = ? AND is_deleted = 0",
            (node_id,)
        )
        return [DocumentRegistryEntry.from_dict(row) for row in rows]
    
    async def merge_entries(
        self,
        entries: List[DocumentRegistryEntry],
    ) -> int:
        """
        Merge entries from another node (gossip receive).
        
        Uses vector clocks for conflict resolution.
        
        Args:
            entries: Entries to merge
            
        Returns:
            Number of entries updated
        """
        updated = 0
        
        for incoming in entries:
            existing = await self.get_entry(incoming.user_id, incoming.document_id)
            
            if existing is None:
                # New entry
                await self._upsert_entry(incoming)
                if incoming.user_id not in self._cache:
                    self._cache[incoming.user_id] = {}
                self._cache[incoming.user_id][incoming.document_id] = incoming
                updated += 1
            else:
                # Compare vector clocks
                if self._vector_clock_greater(incoming.vector_clock, existing.vector_clock):
                    # Incoming is newer
                    await self._upsert_entry(incoming)
                    self._cache[incoming.user_id][incoming.document_id] = incoming
                    updated += 1
                elif self._vector_clocks_concurrent(incoming.vector_clock, existing.vector_clock):
                    # Concurrent updates - merge (prefer non-deleted)
                    merged = self._merge_concurrent(existing, incoming)
                    await self._upsert_entry(merged)
                    self._cache[merged.user_id][merged.document_id] = merged
                    updated += 1
        
        return updated
    
    async def get_all_entries(self, include_deleted: bool = False) -> List[DocumentRegistryEntry]:
        """
        Get all entries in the registry.
        
        Args:
            include_deleted: Include soft-deleted entries
            
        Returns:
            List of all entries
        """
        where = "1=1"
        if not include_deleted:
            where = "is_deleted = 0"
        
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE {where}"
        )
        return [DocumentRegistryEntry.from_dict(row) for row in rows]
    
    async def get_updates_since(
        self,
        since: datetime,
        limit: int = 100,
    ) -> List[DocumentRegistryEntry]:
        """
        Get entries updated since a timestamp.
        
        Args:
            since: Timestamp
            limit: Max entries to return
            
        Returns:
            List of updated entries
        """
        rows = await self.client.fetch_all(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE updated_at > ?
            ORDER BY updated_at
            LIMIT ?
            """,
            (since.isoformat(), limit)
        )
        return [DocumentRegistryEntry.from_dict(row) for row in rows]
    
    async def _upsert_entry(self, entry: DocumentRegistryEntry) -> None:
        """Insert or update an entry."""
        data = entry.to_dict()
        data["vector_clock"] = json.dumps(data["vector_clock"])
        data["is_deleted"] = 1 if data["is_deleted"] else 0
        
        # SQLite UPSERT
        columns = list(data.keys())
        placeholders = ["?" for _ in columns]
        updates = [f"{c} = excluded.{c}" for c in columns if c not in ("user_id", "document_id")]
        
        sql = f"""
            INSERT INTO {self.TABLE_NAME} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT(user_id, document_id) DO UPDATE SET
            {', '.join(updates)}
        """
        
        async with self.client.acquire() as conn:
            await conn.execute(sql, tuple(data.values()))
            await conn.commit()
    
    async def _load_cache(self) -> None:
        """Load all entries into cache."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME}"
        )
        
        self._cache.clear()
        for row in rows:
            entry = DocumentRegistryEntry.from_dict(row)
            if entry.user_id not in self._cache:
                self._cache[entry.user_id] = {}
            self._cache[entry.user_id][entry.document_id] = entry
        
        self._cache_loaded = True
        logger.info(f"Loaded {len(rows)} entries into registry cache")
    
    async def _gossip_loop(self) -> None:
        """Background loop for gossip propagation."""
        import aiohttp
        try:
            while self._running:
                await asyncio.sleep(self.gossip_interval)
                
                # Send pending updates to peers
                if self._pending_updates and self._peer_addresses:
                    await self._send_gossip()
                
                # Periodically do full sync with peers (every 30 seconds)
                if hasattr(self, '_last_full_sync'):
                    if (datetime.now() - self._last_full_sync).total_seconds() > 30:
                        await self._full_sync_with_peers()
                        self._last_full_sync = datetime.now()
                else:
                    self._last_full_sync = datetime.now()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Gossip loop error: {e}")
    
    async def _send_gossip(self) -> None:
        """Send pending updates to peers via HTTP."""
        import aiohttp
        
        if not self._pending_updates:
            return
        
        updates = self._pending_updates.copy()
        self._pending_updates.clear()
        
        # Convert entries to dicts for JSON serialization
        updates_data = [entry.to_dict() for entry in updates]
        
        for peer_address in self._peer_addresses:
            try:
                url = f"http://{peer_address}/api/v1/internal/sync/registry"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"entries": updates_data, "source_node": self.node_id},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            logger.debug(f"Gossiped {len(updates)} updates to {peer_address}")
                        else:
                            logger.warning(f"Gossip to {peer_address} failed: {resp.status}")
            except Exception as e:
                logger.debug(f"Failed to gossip to {peer_address}: {e}")
    
    async def _full_sync_with_peers(self) -> None:
        """Do a full sync with all peers to ensure consistency."""
        import aiohttp
        
        for peer_address in self._peer_addresses:
            try:
                # Get all entries from peer
                url = f"http://{peer_address}/api/v1/internal/sync/registry/all"
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            entries = [DocumentRegistryEntry.from_dict(e) for e in data.get("entries", [])]
                            if entries:
                                merged = await self.merge_entries(entries)
                                logger.debug(f"Full sync from {peer_address}: merged {merged} entries")
            except Exception as e:
                logger.debug(f"Full sync with {peer_address} failed: {e}")
    
    def _vector_clock_greater(
        self,
        vc1: Dict[str, int],
        vc2: Dict[str, int],
    ) -> bool:
        """Check if vc1 > vc2 (happens-after)."""
        all_keys = set(vc1.keys()) | set(vc2.keys())
        
        at_least_one_greater = False
        for key in all_keys:
            v1 = vc1.get(key, 0)
            v2 = vc2.get(key, 0)
            if v1 < v2:
                return False
            if v1 > v2:
                at_least_one_greater = True
        
        return at_least_one_greater
    
    def _vector_clocks_concurrent(
        self,
        vc1: Dict[str, int],
        vc2: Dict[str, int],
    ) -> bool:
        """Check if vc1 and vc2 are concurrent (neither happens-before)."""
        return (
            not self._vector_clock_greater(vc1, vc2) and
            not self._vector_clock_greater(vc2, vc1) and
            vc1 != vc2
        )
    
    def _merge_concurrent(
        self,
        e1: DocumentRegistryEntry,
        e2: DocumentRegistryEntry,
    ) -> DocumentRegistryEntry:
        """Merge two concurrent entries."""
        # Merge vector clocks
        merged_vc = e1.vector_clock.copy()
        for key, val in e2.vector_clock.items():
            merged_vc[key] = max(merged_vc.get(key, 0), val)
        merged_vc[self.node_id] = merged_vc.get(self.node_id, 0) + 1
        
        # DELETE WINS: If either entry is deleted, the merged result is deleted
        # This prevents "resurrection" of deleted documents during sync
        is_deleted = e1.is_deleted or e2.is_deleted
        
        # Use the most recent entry as base for other fields
        if e1.updated_at >= e2.updated_at:
            base = e1
        else:
            base = e2
        
        return DocumentRegistryEntry(
            user_id=base.user_id,
            document_id=base.document_id,
            node_id=base.node_id,
            title=base.title,
            filename=base.filename,
            created_at=min(e1.created_at, e2.created_at),
            updated_at=datetime.now(),
            is_deleted=is_deleted,  # DELETE WINS
            vector_clock=merged_vc,
        )

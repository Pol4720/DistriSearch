"""
Slave Handler for DistriSearch.

Handles slave node operations including:
- Document storage and retrieval
- Local search execution
- Replication handling
- Reporting to master
"""

import asyncio
import logging
import psutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

from .core.vectorization import DocumentVectorizer
from .core.search import QueryProcessor, ResultAggregator, SearchResult

from .communication import (
    HeartbeatClient,
    MasterClient,
    MessageBroker,
    Message,
    MessageType,
)

logger = logging.getLogger(__name__)


class SlaveState(Enum):
    """Slave node state."""
    INITIALIZING = "initializing"
    REGISTERING = "registering"
    ACTIVE = "active"
    SYNCING = "syncing"
    DRAINING = "draining"
    SHUTDOWN = "shutdown"


@dataclass
class SlaveConfig:
    """Configuration for slave handler."""
    
    # Master connection
    master_address: str = "master:8000"
    registration_timeout: float = 30.0
    registration_retries: int = 5
    
    # Heartbeat
    heartbeat_interval: float = 5.0
    
    # Storage
    max_documents: int = 100000
    index_batch_size: int = 100
    
    # Search
    search_timeout: float = 10.0


class SlaveHandler:
    """
    Handler for slave node operations.
    
    Manages:
    - Registration with master
    - Local document storage
    - Search execution
    - Heartbeat reporting
    - Replication requests
    """
    
    def __init__(
        self,
        node_id: str,
        address: str,
        message_broker: MessageBroker,
        config: Optional[SlaveConfig] = None,
    ):
        """
        Initialize slave handler.
        
        Args:
            node_id: This node's ID
            address: This node's address
            message_broker: Message broker for events
            config: Slave configuration
        """
        self.node_id = node_id
        self.address = address
        self.message_broker = message_broker
        self.config = config or SlaveConfig()
        
        # State
        self._state = SlaveState.INITIALIZING
        self._master_id: Optional[str] = None
        self._running = False
        
        # Clients
        self._master_client: Optional[MasterClient] = None
        self._heartbeat_client: Optional[HeartbeatClient] = None
        
        # Document storage (in-memory for now)
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._document_vectors: Dict[str, Any] = {}
        
        # Vectorizer
        self._vectorizer = DocumentVectorizer()
        
        # Search components
        self._query_processor: Optional[QueryProcessor] = None
        self._result_aggregator: Optional[ResultAggregator] = None
        
        # Statistics
        self._indexed_count = 0
        self._search_count = 0
        self._replica_count = 0
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Background tasks
        self._sync_task: Optional[asyncio.Task] = None
        
        logger.info(f"SlaveHandler initialized for node {node_id}")
    
    @property
    def state(self) -> SlaveState:
        """Get current state."""
        return self._state
    
    @property
    def documents_count(self) -> int:
        """Get number of stored documents."""
        return len(self._documents)
    
    async def start(self):
        """Start the slave handler."""
        if self._running:
            return
        
        self._running = True
        self._state = SlaveState.REGISTERING
        
        # Initialize master client
        self._master_client = MasterClient(
            master_address=self.config.master_address,
            timeout=self.config.registration_timeout,
        )
        
        # Register with master
        registered = await self._register_with_master()
        
        if registered:
            self._state = SlaveState.ACTIVE
            
            # Start heartbeat client
            self._heartbeat_client = HeartbeatClient(
                node_id=self.node_id,
                master_url=f"http://{self.config.master_address}/api/heartbeat",
                interval=self.config.heartbeat_interval,
                stats_collector=self._collect_stats,
            )
            await self._heartbeat_client.start()
            
            # Start background sync
            self._sync_task = asyncio.create_task(self._sync_loop())
            
            logger.info("SlaveHandler started and registered")
        else:
            logger.error("Failed to register with master")
            self._state = SlaveState.SHUTDOWN
    
    async def stop(self):
        """Stop the slave handler."""
        self._running = False
        self._state = SlaveState.SHUTDOWN
        
        # Stop heartbeat
        if self._heartbeat_client:
            await self._heartbeat_client.stop()
        
        # Stop sync task
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        # Deregister from master
        if self._master_client:
            try:
                await self._master_client.deregister_node(self.node_id)
            except:
                pass
            await self._master_client.close()
        
        logger.info("SlaveHandler stopped")
    
    async def _register_with_master(self) -> bool:
        """Register this node with the master."""
        for attempt in range(self.config.registration_retries):
            try:
                response = await self._master_client.register_node(
                    node_id=self.node_id,
                    node_address=self.address,
                    capabilities={
                        "max_documents": self.config.max_documents,
                        "version": "1.0.0",
                    },
                )
                
                if response.success:
                    self._master_id = response.data.get("master_id")
                    logger.info(
                        f"Registered with master {self._master_id}"
                    )
                    return True
                    
            except Exception as e:
                logger.warning(
                    f"Registration attempt {attempt + 1} failed: {e}"
                )
            
            await asyncio.sleep(2.0 * (attempt + 1))
        
        return False
    
    def _collect_stats(self) -> Dict[str, Any]:
        """Collect current node statistics for heartbeat."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Calculate load (normalized 0-1)
            load = (
                0.4 * (cpu_percent / 100) +
                0.3 * (memory.percent / 100) +
                0.3 * (self.documents_count / self.config.max_documents)
            )
            
            return {
                "documents_count": self.documents_count,
                "load": min(1.0, load),
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "indexed_count": self._indexed_count,
                "search_count": self._search_count,
                "replica_count": self._replica_count,
                "state": self._state.value,
            }
        except Exception as e:
            logger.warning(f"Error collecting stats: {e}")
            return {
                "documents_count": self.documents_count,
                "load": 0.5,
            }
    
    # Document operations
    
    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Index a document locally.
        
        Args:
            doc_id: Document ID
            content: Document content
            metadata: Document metadata
            
        Returns:
            True if indexed successfully
        """
        if self.documents_count >= self.config.max_documents:
            logger.warning("Document limit reached")
            return False
        
        async with self._lock:
            try:
                # Vectorize document
                vector = self._vectorizer.vectorize(content)
                
                # Store document
                self._documents[doc_id] = {
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata or {},
                    "indexed_at": datetime.now().isoformat(),
                    "is_replica": (metadata or {}).get("is_replica", False),
                }
                
                # Store vector
                self._document_vectors[doc_id] = vector
                
                self._indexed_count += 1
                
                if (metadata or {}).get("is_replica"):
                    self._replica_count += 1
                
                logger.debug(f"Indexed document {doc_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error indexing document {doc_id}: {e}")
                return False
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document data or None
        """
        return self._documents.get(doc_id)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            True if deleted
        """
        async with self._lock:
            if doc_id in self._documents:
                was_replica = self._documents[doc_id].get("is_replica", False)
                
                del self._documents[doc_id]
                self._document_vectors.pop(doc_id, None)
                
                if was_replica:
                    self._replica_count -= 1
                
                logger.debug(f"Deleted document {doc_id}")
                return True
            
            return False
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute local search.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Search filters
            
        Returns:
            List of search results
        """
        try:
            self._search_count += 1
            
            # Vectorize query
            query_vector = self._vectorizer.vectorize(query)
            
            # Search documents
            results = []
            
            for doc_id, doc in self._documents.items():
                # Apply filters
                if filters:
                    metadata = doc.get("metadata", {})
                    if not self._matches_filters(metadata, filters):
                        continue
                
                # Calculate similarity
                doc_vector = self._document_vectors.get(doc_id)
                if doc_vector:
                    score = self._calculate_similarity(query_vector, doc_vector)
                    
                    results.append({
                        "id": doc_id,
                        "score": score,
                        "content": doc.get("content", "")[:500],  # Snippet
                        "metadata": doc.get("metadata", {}),
                        "node_id": self.node_id,
                    })
            
            # Sort by score
            results.sort(key=lambda r: r["score"], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def _matches_filters(
        self,
        metadata: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True
    
    def _calculate_similarity(
        self,
        query_vector: Any,
        doc_vector: Any,
    ) -> float:
        """Calculate similarity between query and document vectors."""
        # Simplified - real implementation uses proper vector similarity
        try:
            # Use TF-IDF cosine similarity
            if hasattr(query_vector, 'tfidf') and hasattr(doc_vector, 'tfidf'):
                from numpy import dot
                from numpy.linalg import norm
                
                a = query_vector.tfidf
                b = doc_vector.tfidf
                
                if norm(a) > 0 and norm(b) > 0:
                    return float(dot(a, b) / (norm(a) * norm(b)))
            
            return 0.0
        except:
            return 0.0
    
    # Replication
    
    async def replicate_from(
        self,
        source_node_address: str,
        doc_id: str,
    ) -> bool:
        """
        Replicate a document from another node.
        
        Args:
            source_node_address: Source node address
            doc_id: Document ID to replicate
            
        Returns:
            True if replicated successfully
        """
        try:
            from .communication import NodeClient
            
            client = NodeClient(node_address=source_node_address)
            response = await client.get_document(doc_id)
            
            if response.success and response.data:
                doc = response.data
                return await self.index_document(
                    doc_id=doc_id,
                    content=doc.get("content", ""),
                    metadata={
                        **doc.get("metadata", {}),
                        "is_replica": True,
                        "source_node": source_node_address,
                    },
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Replication error for {doc_id}: {e}")
            return False
    
    # Background tasks
    
    async def _sync_loop(self):
        """Periodically sync state with master."""
        try:
            while self._running:
                await asyncio.sleep(60.0)  # Sync every minute
                
                # Report stats to master
                if self._master_client:
                    try:
                        stats = self._collect_stats()
                        await self._master_client.report_stats(
                            self.node_id,
                            stats,
                        )
                    except Exception as e:
                        logger.warning(f"Stats report error: {e}")
                        
        except asyncio.CancelledError:
            pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler status."""
        return {
            "node_id": self.node_id,
            "state": self._state.value,
            "master_id": self._master_id,
            "documents_count": self.documents_count,
            "replica_count": self._replica_count,
            "indexed_count": self._indexed_count,
            "search_count": self._search_count,
            "running": self._running,
            **self._collect_stats(),
        }

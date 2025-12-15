# -*- coding: utf-8 -*-
"""
Replica Tracker - Tracks document replicas across the cluster.

Maintains state of all replicas for consistency and failure recovery.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ReplicaStatus(Enum):
    """Status of a replica."""
    ACTIVE = "active"
    SYNCING = "syncing"
    STALE = "stale"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ReplicaInfo:
    """Information about a document replica."""
    document_id: str
    node_id: str
    is_primary: bool
    status: ReplicaStatus = ReplicaStatus.ACTIVE
    version: int = 1
    last_sync: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    checksum: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        return self.status in (ReplicaStatus.ACTIVE, ReplicaStatus.SYNCING)


@dataclass
class DocumentReplicas:
    """All replicas for a document."""
    document_id: str
    primary: Optional[ReplicaInfo] = None
    replicas: List[ReplicaInfo] = field(default_factory=list)
    replication_factor: int = 2
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def all_replicas(self) -> List[ReplicaInfo]:
        result = []
        if self.primary:
            result.append(self.primary)
        result.extend(self.replicas)
        return result
    
    @property
    def healthy_count(self) -> int:
        return sum(1 for r in self.all_replicas if r.is_healthy)
    
    @property
    def is_under_replicated(self) -> bool:
        return self.healthy_count < self.replication_factor
    
    @property
    def all_nodes(self) -> List[str]:
        return [r.node_id for r in self.all_replicas]


class ReplicaTracker:
    """
    Tracks all document replicas in the cluster.
    
    Provides:
    - Replica state management
    - Under-replication detection
    - Node-to-replica mapping
    - Version tracking for consistency
    """
    
    def __init__(self, default_replication_factor: int = 2):
        """
        Initialize replica tracker.
        
        Args:
            default_replication_factor: Default number of replicas
        """
        self.default_replication_factor = default_replication_factor
        
        # Storage
        self._documents: Dict[str, DocumentReplicas] = {}
        self._node_replicas: Dict[str, Set[str]] = defaultdict(set)  # node_id -> doc_ids
        self._under_replicated: Set[str] = set()
    
    def register_document(
        self,
        document_id: str,
        primary_node: str,
        replica_nodes: Optional[List[str]] = None,
        replication_factor: Optional[int] = None,
        size_bytes: int = 0,
        checksum: Optional[str] = None
    ) -> DocumentReplicas:
        """
        Register a new document with its replicas.
        
        Args:
            document_id: Document identifier
            primary_node: Node storing the primary
            replica_nodes: Nodes storing replicas
            replication_factor: Required replication factor
            size_bytes: Document size
            checksum: Document checksum
            
        Returns:
            Document replicas info
        """
        repl_factor = replication_factor or self.default_replication_factor
        
        # Create primary replica info
        primary = ReplicaInfo(
            document_id=document_id,
            node_id=primary_node,
            is_primary=True,
            status=ReplicaStatus.ACTIVE,
            size_bytes=size_bytes,
            checksum=checksum
        )
        
        # Create replica infos
        replicas = []
        for node_id in (replica_nodes or []):
            replica = ReplicaInfo(
                document_id=document_id,
                node_id=node_id,
                is_primary=False,
                status=ReplicaStatus.SYNCING,  # Initially syncing
                size_bytes=size_bytes,
                checksum=checksum
            )
            replicas.append(replica)
        
        doc_replicas = DocumentReplicas(
            document_id=document_id,
            primary=primary,
            replicas=replicas,
            replication_factor=repl_factor
        )
        
        self._documents[document_id] = doc_replicas
        
        # Update indexes
        self._node_replicas[primary_node].add(document_id)
        for replica in replicas:
            self._node_replicas[replica.node_id].add(document_id)
        
        # Check replication status
        if doc_replicas.is_under_replicated:
            self._under_replicated.add(document_id)
        
        logger.debug(f"Registered document {document_id} with {len(replicas)} replicas")
        
        return doc_replicas
    
    def add_replica(
        self,
        document_id: str,
        node_id: str,
        size_bytes: int = 0,
        checksum: Optional[str] = None
    ) -> Optional[ReplicaInfo]:
        """
        Add a new replica for a document.
        
        Args:
            document_id: Document to replicate
            node_id: Node for the new replica
            size_bytes: Document size
            checksum: Document checksum
            
        Returns:
            Created replica info
        """
        doc = self._documents.get(document_id)
        if not doc:
            logger.warning(f"Document not found: {document_id}")
            return None
        
        # Check if already exists on this node
        if node_id in doc.all_nodes:
            logger.warning(f"Replica already exists on {node_id}")
            return None
        
        replica = ReplicaInfo(
            document_id=document_id,
            node_id=node_id,
            is_primary=False,
            status=ReplicaStatus.PENDING,
            size_bytes=size_bytes or (doc.primary.size_bytes if doc.primary else 0),
            checksum=checksum or (doc.primary.checksum if doc.primary else None)
        )
        
        doc.replicas.append(replica)
        self._node_replicas[node_id].add(document_id)
        
        # Update under-replication status
        if not doc.is_under_replicated:
            self._under_replicated.discard(document_id)
        
        return replica
    
    def remove_replica(
        self,
        document_id: str,
        node_id: str
    ) -> bool:
        """
        Remove a replica from a node.
        
        Args:
            document_id: Document ID
            node_id: Node to remove replica from
            
        Returns:
            True if removed
        """
        doc = self._documents.get(document_id)
        if not doc:
            return False
        
        # Cannot remove primary
        if doc.primary and doc.primary.node_id == node_id:
            logger.warning("Cannot remove primary replica directly")
            return False
        
        # Find and remove replica
        for i, replica in enumerate(doc.replicas):
            if replica.node_id == node_id:
                doc.replicas.pop(i)
                self._node_replicas[node_id].discard(document_id)
                
                # Update under-replication
                if doc.is_under_replicated:
                    self._under_replicated.add(document_id)
                
                return True
        
        return False
    
    def update_replica_status(
        self,
        document_id: str,
        node_id: str,
        status: ReplicaStatus,
        version: Optional[int] = None
    ) -> bool:
        """
        Update status of a replica.
        
        Args:
            document_id: Document ID
            node_id: Node with the replica
            status: New status
            version: New version number
            
        Returns:
            True if updated
        """
        doc = self._documents.get(document_id)
        if not doc:
            return False
        
        for replica in doc.all_replicas:
            if replica.node_id == node_id:
                replica.status = status
                replica.last_sync = datetime.utcnow()
                if version is not None:
                    replica.version = version
                
                # Update under-replication tracking
                if doc.is_under_replicated:
                    self._under_replicated.add(document_id)
                else:
                    self._under_replicated.discard(document_id)
                
                return True
        
        return False
    
    def promote_replica_to_primary(
        self,
        document_id: str,
        new_primary_node: str
    ) -> bool:
        """
        Promote a replica to primary (for failover).
        
        Args:
            document_id: Document ID
            new_primary_node: Node to promote
            
        Returns:
            True if promoted
        """
        doc = self._documents.get(document_id)
        if not doc:
            return False
        
        # Find replica to promote
        replica_idx = None
        for i, replica in enumerate(doc.replicas):
            if replica.node_id == new_primary_node:
                replica_idx = i
                break
        
        if replica_idx is None:
            logger.warning(f"No replica on {new_primary_node} to promote")
            return False
        
        # Demote old primary if exists
        if doc.primary:
            old_primary = doc.primary
            old_primary.is_primary = False
            doc.replicas.append(old_primary)
        
        # Promote replica
        new_primary = doc.replicas.pop(replica_idx)
        new_primary.is_primary = True
        doc.primary = new_primary
        
        logger.info(f"Promoted replica on {new_primary_node} to primary for {document_id}")
        
        return True
    
    def mark_node_failed(self, node_id: str) -> List[str]:
        """
        Mark all replicas on a node as failed.
        
        Args:
            node_id: Failed node
            
        Returns:
            List of affected document IDs
        """
        affected = []
        
        for doc_id in list(self._node_replicas.get(node_id, [])):
            doc = self._documents.get(doc_id)
            if not doc:
                continue
            
            for replica in doc.all_replicas:
                if replica.node_id == node_id:
                    replica.status = ReplicaStatus.FAILED
            
            if doc.is_under_replicated:
                self._under_replicated.add(doc_id)
            
            affected.append(doc_id)
        
        logger.warning(f"Marked {len(affected)} replicas as failed on node {node_id}")
        
        return affected
    
    def get_document_replicas(self, document_id: str) -> Optional[DocumentReplicas]:
        """Get all replicas for a document."""
        return self._documents.get(document_id)
    
    def get_replicas_on_node(self, node_id: str) -> List[ReplicaInfo]:
        """Get all replicas stored on a node."""
        replicas = []
        
        for doc_id in self._node_replicas.get(node_id, []):
            doc = self._documents.get(doc_id)
            if doc:
                for replica in doc.all_replicas:
                    if replica.node_id == node_id:
                        replicas.append(replica)
        
        return replicas
    
    def get_under_replicated(self) -> List[str]:
        """Get all under-replicated document IDs."""
        return list(self._under_replicated)
    
    def get_documents_needing_replication(
        self,
        limit: int = 100
    ) -> List[DocumentReplicas]:
        """
        Get documents that need more replicas.
        
        Args:
            limit: Maximum documents to return
            
        Returns:
            List of under-replicated documents
        """
        result = []
        
        for doc_id in list(self._under_replicated)[:limit]:
            doc = self._documents.get(doc_id)
            if doc and doc.is_under_replicated:
                result.append(doc)
        
        return result
    
    def get_node_document_count(self, node_id: str) -> int:
        """Get number of documents on a node."""
        return len(self._node_replicas.get(node_id, []))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get replication statistics."""
        total_docs = len(self._documents)
        total_replicas = sum(
            len(doc.all_replicas) for doc in self._documents.values()
        )
        
        status_counts = defaultdict(int)
        for doc in self._documents.values():
            for replica in doc.all_replicas:
                status_counts[replica.status.value] += 1
        
        return {
            "total_documents": total_docs,
            "total_replicas": total_replicas,
            "under_replicated_count": len(self._under_replicated),
            "avg_replicas_per_doc": total_replicas / total_docs if total_docs > 0 else 0,
            "nodes_with_replicas": len(self._node_replicas),
            "status_distribution": dict(status_counts),
            "default_replication_factor": self.default_replication_factor
        }
    
    def export_state(self) -> Dict[str, Any]:
        """Export tracker state for persistence."""
        return {
            "documents": {
                doc_id: {
                    "primary_node": doc.primary.node_id if doc.primary else None,
                    "replica_nodes": [r.node_id for r in doc.replicas],
                    "replication_factor": doc.replication_factor
                }
                for doc_id, doc in self._documents.items()
            },
            "default_replication_factor": self.default_replication_factor
        }

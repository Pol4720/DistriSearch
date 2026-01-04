"""
SQLite Cluster Repository for DistriSearch.

Handles storage of cluster metadata in SQLite:
- Nodes (cluster membership)
- Partitions (VP-Tree assignments)

This is replicated via Raft for AP mode.
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from .sqlite_client import SQLiteClient
from .models import NodeModel, PartitionModel, NodeStatus, NodeRole

logger = logging.getLogger(__name__)


class SQLiteNodeRepository:
    """
    Repository for node operations using SQLite.
    
    Manages cluster membership information.
    """
    
    TABLE_NAME = "nodes"
    
    def __init__(self, client: SQLiteClient):
        """
        Initialize node repository.
        
        Args:
            client: SQLite client instance
        """
        self.client = client
    
    async def ensure_indexes(self) -> None:
        """Indexes are created in schema."""
        pass
    
    async def create(self, node: NodeModel) -> str:
        """
        Register a new node.
        
        Args:
            node: Node model
            
        Returns:
            Node ID
        """
        data = self._node_to_row(node)
        await self.client.insert(self.TABLE_NAME, data)
        logger.info(f"Registered node: {node.id} at {node.address}")
        return node.id
    
    async def find_by_id(self, node_id: str) -> Optional[NodeModel]:
        """Find node by ID."""
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",
            (node_id,)
        )
        return self._row_to_node(row) if row else None
    
    async def find_by_address(self, address: str) -> Optional[NodeModel]:
        """Find node by address."""
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE address = ?",
            (address,)
        )
        return self._row_to_node(row) if row else None
    
    async def get_all(self) -> List[NodeModel]:
        """Get all nodes."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} ORDER BY created_at"
        )
        return [self._row_to_node(row) for row in rows]
    
    async def get_active_nodes(self) -> List[NodeModel]:
        """Get all active nodes."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE status = 'active' ORDER BY created_at"
        )
        return [self._row_to_node(row) for row in rows]
    
    async def get_by_role(self, role: NodeRole) -> List[NodeModel]:
        """Get nodes by role."""
        role_value = role.value if hasattr(role, 'value') else role
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE role = ?",
            (role_value,)
        )
        return [self._row_to_node(row) for row in rows]
    
    async def update(self, node_id: str, update_data: Dict[str, Any]) -> bool:
        """Update node data."""
        # Serialize complex types
        serialized = {}
        for key, value in update_data.items():
            if isinstance(value, (list, dict)):
                serialized[key] = json.dumps(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                serialized[key] = value.value
            else:
                serialized[key] = value
        
        return await self.client.update(self.TABLE_NAME, node_id, serialized)
    
    async def update_heartbeat(self, node_id: str, load: float = 0.0, documents_count: int = 0) -> bool:
        """Update node heartbeat."""
        return await self.update(node_id, {
            "last_heartbeat": datetime.now().isoformat(),
            "load": load,
            "documents_count": documents_count,
            "status": "active",
        })
    
    async def update_status(self, node_id: str, status: NodeStatus) -> bool:
        """Update node status."""
        status_value = status.value if hasattr(status, 'value') else status
        return await self.update(node_id, {"status": status_value})
    
    async def delete(self, node_id: str) -> bool:
        """Remove a node."""
        success = await self.client.delete(self.TABLE_NAME, node_id)
        if success:
            logger.info(f"Removed node: {node_id}")
        return success
    
    async def count(self, status: Optional[NodeStatus] = None) -> int:
        """Count nodes."""
        if status:
            status_value = status.value if hasattr(status, 'value') else status
            return await self.client.fetch_count(self.TABLE_NAME, "status = ?", (status_value,))
        return await self.client.fetch_count(self.TABLE_NAME)
    
    def _node_to_row(self, node: NodeModel) -> Dict[str, Any]:
        """Convert NodeModel to row."""
        return {
            "id": node.id,
            "name": node.name,
            "address": node.address,
            "port": node.port,
            "role": node.role.value if hasattr(node.role, 'value') else node.role,
            "status": node.status.value if hasattr(node.status, 'value') else node.status,
            "cpu_cores": node.cpu_cores,
            "memory_mb": node.memory_mb,
            "disk_gb": node.disk_gb,
            "documents_count": node.documents_count,
            "partition_ids": json.dumps(node.partition_ids) if node.partition_ids else "[]",
            "load": node.load,
            "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
            "health_score": node.health_score,
            "metadata": json.dumps(node.metadata) if node.metadata else "{}",
            "created_at": node.created_at.isoformat() if node.created_at else datetime.now().isoformat(),
            "updated_at": node.updated_at.isoformat() if node.updated_at else datetime.now().isoformat(),
        }
    
    def _row_to_node(self, row: Dict[str, Any]) -> NodeModel:
        """Convert row to NodeModel."""
        if row is None:
            return None
        
        def parse_json(value, default):
            if value is None:
                return default
            if isinstance(value, (list, dict)):
                return value
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default
        
        def parse_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        
        return NodeModel(
            id=row["id"],
            name=row.get("name"),
            address=row["address"],
            port=row.get("port", 8000),
            role=NodeRole(row.get("role", "slave")),
            status=NodeStatus(row.get("status", "active")),
            cpu_cores=row.get("cpu_cores"),
            memory_mb=row.get("memory_mb"),
            disk_gb=row.get("disk_gb"),
            documents_count=row.get("documents_count", 0),
            partition_ids=parse_json(row.get("partition_ids"), []),
            load=row.get("load", 0.0),
            last_heartbeat=parse_datetime(row.get("last_heartbeat")),
            health_score=row.get("health_score", 1.0),
            metadata=parse_json(row.get("metadata"), {}),
            created_at=parse_datetime(row.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(row.get("updated_at")) or datetime.now(),
        )


class SQLitePartitionRepository:
    """
    Repository for partition operations using SQLite.
    
    Manages VP-Tree partition assignments.
    """
    
    TABLE_NAME = "partitions"
    
    def __init__(self, client: SQLiteClient):
        """
        Initialize partition repository.
        
        Args:
            client: SQLite client instance
        """
        self.client = client
    
    async def ensure_indexes(self) -> None:
        """Indexes are created in schema."""
        pass
    
    async def create(self, partition: PartitionModel) -> str:
        """Create a new partition."""
        data = self._partition_to_row(partition)
        await self.client.insert(self.TABLE_NAME, data)
        logger.info(f"Created partition: {partition.id}")
        return partition.id
    
    async def find_by_id(self, partition_id: str) -> Optional[PartitionModel]:
        """Find partition by ID."""
        row = await self.client.fetch_one(
            f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",
            (partition_id,)
        )
        return self._row_to_partition(row) if row else None
    
    async def get_all(self) -> List[PartitionModel]:
        """Get all partitions."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} ORDER BY created_at"
        )
        return [self._row_to_partition(row) for row in rows]
    
    async def get_active(self) -> List[PartitionModel]:
        """Get active partitions."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE is_active = 1"
        )
        return [self._row_to_partition(row) for row in rows]
    
    async def get_by_node(self, node_id: str) -> List[PartitionModel]:
        """Get partitions assigned to a node."""
        rows = await self.client.fetch_all(
            f"SELECT * FROM {self.TABLE_NAME} WHERE primary_node_id = ?",
            (node_id,)
        )
        return [self._row_to_partition(row) for row in rows]
    
    async def update(self, partition_id: str, update_data: Dict[str, Any]) -> bool:
        """Update partition data."""
        serialized = {}
        for key, value in update_data.items():
            if isinstance(value, (list, dict)):
                serialized[key] = json.dumps(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, bool):
                serialized[key] = 1 if value else 0
            else:
                serialized[key] = value
        
        return await self.client.update(self.TABLE_NAME, partition_id, serialized)
    
    async def assign_to_node(self, partition_id: str, node_id: str) -> bool:
        """Assign partition to a node."""
        return await self.update(partition_id, {"primary_node_id": node_id})
    
    async def add_replica(self, partition_id: str, replica_node_id: str) -> bool:
        """Add a replica node to partition."""
        partition = await self.find_by_id(partition_id)
        if not partition:
            return False
        
        replicas = list(partition.replica_node_ids)
        if replica_node_id not in replicas:
            replicas.append(replica_node_id)
            return await self.update(partition_id, {"replica_node_ids": replicas})
        return True
    
    async def remove_replica(self, partition_id: str, replica_node_id: str) -> bool:
        """Remove a replica node from partition."""
        partition = await self.find_by_id(partition_id)
        if not partition:
            return False
        
        replicas = [r for r in partition.replica_node_ids if r != replica_node_id]
        return await self.update(partition_id, {"replica_node_ids": replicas})
    
    async def delete(self, partition_id: str) -> bool:
        """Delete a partition."""
        return await self.client.delete(self.TABLE_NAME, partition_id)
    
    async def count(self, active_only: bool = False) -> int:
        """Count partitions."""
        if active_only:
            return await self.client.fetch_count(self.TABLE_NAME, "is_active = 1")
        return await self.client.fetch_count(self.TABLE_NAME)
    
    def _partition_to_row(self, partition: PartitionModel) -> Dict[str, Any]:
        """Convert PartitionModel to row."""
        return {
            "id": partition.id,
            "name": partition.name,
            "primary_node_id": partition.primary_node_id,
            "replica_node_ids": json.dumps(partition.replica_node_ids) if partition.replica_node_ids else "[]",
            "document_ids": json.dumps(partition.document_ids) if partition.document_ids else "[]",
            "documents_count": partition.documents_count,
            "centroid_vector": json.dumps(partition.centroid_vector) if partition.centroid_vector else None,
            "radius": partition.radius,
            "is_active": 1 if partition.is_active else 0,
            "is_rebalancing": 1 if partition.is_rebalancing else 0,
            "created_at": partition.created_at.isoformat() if partition.created_at else datetime.now().isoformat(),
            "updated_at": partition.updated_at.isoformat() if partition.updated_at else datetime.now().isoformat(),
        }
    
    def _row_to_partition(self, row: Dict[str, Any]) -> PartitionModel:
        """Convert row to PartitionModel."""
        if row is None:
            return None
        
        def parse_json(value, default):
            if value is None:
                return default
            if isinstance(value, (list, dict)):
                return value
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default
        
        def parse_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        
        return PartitionModel(
            id=row["id"],
            name=row.get("name"),
            primary_node_id=row.get("primary_node_id"),
            replica_node_ids=parse_json(row.get("replica_node_ids"), []),
            document_ids=parse_json(row.get("document_ids"), []),
            documents_count=row.get("documents_count", 0),
            centroid_vector=parse_json(row.get("centroid_vector"), None),
            radius=row.get("radius", 0.0),
            is_active=bool(row.get("is_active", 1)),
            is_rebalancing=bool(row.get("is_rebalancing", 0)),
            created_at=parse_datetime(row.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(row.get("updated_at")) or datetime.now(),
        )

"""
MongoDB Client and Repositories for DistriSearch.

Provides database connectivity and CRUD operations
for all entities in the system.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, TypeVar, Generic
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
from pymongo.errors import DuplicateKeyError, ConnectionFailure

from app.storage.models import (
    DocumentModel,
    NodeModel,
    PartitionModel,
    SearchQueryModel,
    MetricsModel,
    DocumentStatus,
    NodeStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MongoDBClient:
    """
    MongoDB client with connection management.
    
    Features:
    - Connection pooling
    - Automatic reconnection
    - Index management
    """
    
    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        database_name: str = "distrisearch",
        max_pool_size: int = 100,
        min_pool_size: int = 10,
    ):
        """
        Initialize MongoDB client.
        
        Args:
            uri: MongoDB connection URI
            database_name: Database name
            max_pool_size: Maximum connection pool size
            min_pool_size: Minimum connection pool size
        """
        self.uri = uri
        self.database_name = database_name
        self.max_pool_size = max_pool_size
        self.min_pool_size = min_pool_size
        
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
        
        logger.info(f"MongoDB client initialized for {database_name}")
    
    async def connect(self):
        """Connect to MongoDB."""
        if self._connected:
            return
        
        try:
            self._client = AsyncIOMotorClient(
                self.uri,
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
            )
            
            # Verify connection
            await self._client.admin.command('ping')
            
            self._db = self._client[self.database_name]
            self._connected = True
            
            # Create indexes
            await self._create_indexes()
            
            logger.info("Connected to MongoDB")
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self._db is None:
            raise RuntimeError("Not connected to MongoDB")
        return self._db
    
    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get database instance (alias for db)."""
        return self.db
    
    async def _create_indexes(self):
        """Create database indexes."""
        # Documents collection indexes
        documents = self.db.documents
        await documents.create_indexes([
            IndexModel([("status", ASCENDING)]),
            IndexModel([("primary_node_id", ASCENDING)]),
            IndexModel([("partition_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("content", TEXT)]),
        ])
        
        # Nodes collection indexes
        nodes = self.db.nodes
        await nodes.create_indexes([
            IndexModel([("address", ASCENDING)], unique=True),
            IndexModel([("role", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ])
        
        # Partitions collection indexes
        partitions = self.db.partitions
        await partitions.create_indexes([
            IndexModel([("primary_node_id", ASCENDING)]),
            IndexModel([("is_active", ASCENDING)]),
        ])
        
        # Search queries collection indexes
        queries = self.db.search_queries
        await queries.create_indexes([
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
        ])
        
        # Metrics collection indexes (TTL for auto-cleanup)
        metrics = self.db.metrics
        await metrics.create_indexes([
            IndexModel([("node_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("metric_type", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel(
                [("timestamp", ASCENDING)],
                expireAfterSeconds=86400 * 7,  # 7 days TTL
            ),
        ])
        
        logger.info("Database indexes created")
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            await self._client.admin.command('ping')
            return True
        except:
            return False
    
    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        """Get a collection by name."""
        return self.db[name]


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""
    
    def __init__(
        self,
        client: MongoDBClient,
        collection_name: str,
    ):
        """
        Initialize repository.
        
        Args:
            client: MongoDB client
            collection_name: Collection name
        """
        self.client = client
        self.collection_name = collection_name
    
    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Get collection."""
        return self.client.get_collection(self.collection_name)
    
    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Find document by ID."""
        return await self.collection.find_one({"_id": id})
    
    async def find_many(
        self,
        filter: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort: Optional[List[tuple]] = None,
    ) -> List[Dict[str, Any]]:
        """Find multiple documents."""
        cursor = self.collection.find(filter)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def count(self, filter: Dict[str, Any] = None) -> int:
        """Count documents."""
        return await self.collection.count_documents(filter or {})
    
    async def insert_one(self, document: Dict[str, Any]) -> str:
        """Insert one document."""
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)
    
    async def update_one(
        self,
        id: str,
        update: Dict[str, Any],
    ) -> bool:
        """Update one document."""
        result = await self.collection.update_one(
            {"_id": id},
            {"$set": {**update, "updated_at": datetime.now()}},
        )
        return result.modified_count > 0
    
    async def delete_one(self, id: str) -> bool:
        """Delete one document."""
        result = await self.collection.delete_one({"_id": id})
        return result.deleted_count > 0
    
    async def delete_many(self, filter: Dict[str, Any]) -> int:
        """Delete multiple documents."""
        result = await self.collection.delete_many(filter)
        return result.deleted_count


class DocumentRepository(BaseRepository[DocumentModel]):
    """Repository for document operations."""
    
    def __init__(self, client: MongoDBClient):
        super().__init__(client, "documents")
    
    async def ensure_indexes(self):
        """Ensure indexes exist for the documents collection."""
        await self.collection.create_indexes([
            IndexModel([("status", ASCENDING)]),
            IndexModel([("primary_node_id", ASCENDING)]),
            IndexModel([("partition_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ])
    
    async def create(self, document: DocumentModel) -> str:
        """Create a new document."""
        try:
            return await self.insert_one(document.to_dict())
        except DuplicateKeyError:
            logger.warning(f"Document {document.id} already exists")
            return document.id
    
    async def get(self, id: str) -> Optional[DocumentModel]:
        """Get document by ID."""
        data = await self.find_by_id(id)
        return DocumentModel.from_dict(data) if data else None
    
    async def update(self, id: str, update: Dict[str, Any]) -> bool:
        """Update document."""
        return await self.update_one(id, update)
    
    async def delete(self, id: str) -> bool:
        """Delete document."""
        return await self.delete_one(id)
    
    async def get_by_status(
        self,
        status: DocumentStatus,
        limit: int = 100,
    ) -> List[DocumentModel]:
        """Get documents by status."""
        docs = await self.find_many(
            {"status": status.value},
            limit=limit,
            sort=[("created_at", DESCENDING)],
        )
        return [DocumentModel.from_dict(d) for d in docs]
    
    async def get_by_node(
        self,
        node_id: str,
        limit: int = 1000,
    ) -> List[DocumentModel]:
        """Get documents on a node."""
        docs = await self.find_many(
            {"primary_node_id": node_id},
            limit=limit,
        )
        return [DocumentModel.from_dict(d) for d in docs]
    
    async def get_by_partition(
        self,
        partition_id: str,
        limit: int = 1000,
    ) -> List[DocumentModel]:
        """Get documents in a partition."""
        docs = await self.find_many(
            {"partition_id": partition_id},
            limit=limit,
        )
        return [DocumentModel.from_dict(d) for d in docs]
    
    async def search_text(
        self,
        query: str,
        limit: int = 10,
    ) -> List[DocumentModel]:
        """Full-text search on content."""
        cursor = self.collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [DocumentModel.from_dict(d) for d in docs]
    
    async def mark_indexed(
        self,
        id: str,
        node_id: str,
        partition_id: str,
    ):
        """Mark document as indexed."""
        await self.update(id, {
            "status": DocumentStatus.INDEXED.value,
            "primary_node_id": node_id,
            "partition_id": partition_id,
            "indexed_at": datetime.now(),
        })


class ClusterRepository:
    """
    Repository for cluster-related operations.
    
    Manages nodes and partitions.
    """
    
    def __init__(self, client: MongoDBClient):
        self.client = client
        self._nodes = BaseRepository[NodeModel](client, "nodes")
        self._partitions = BaseRepository[PartitionModel](client, "partitions")
    
    async def ensure_indexes(self):
        """Ensure indexes exist for cluster-related collections."""
        # Indexes are already created by MongoDBClient._create_indexes
        # This method exists for consistency with other repositories
        pass
    
    # Node operations
    
    async def create_node(self, node: NodeModel) -> str:
        """Create a new node."""
        return await self._nodes.insert_one(node.to_dict())
    
    async def get_node(self, id: str) -> Optional[NodeModel]:
        """Get node by ID."""
        data = await self._nodes.find_by_id(id)
        return NodeModel.from_dict(data) if data else None
    
    async def get_node_by_address(self, address: str) -> Optional[NodeModel]:
        """Get node by address."""
        docs = await self._nodes.find_many({"address": address}, limit=1)
        return NodeModel.from_dict(docs[0]) if docs else None
    
    async def get_all_nodes(self) -> List[NodeModel]:
        """Get all nodes."""
        docs = await self._nodes.find_many({}, limit=1000)
        return [NodeModel.from_dict(d) for d in docs]
    
    async def get_active_nodes(self) -> List[NodeModel]:
        """Get all active nodes."""
        docs = await self._nodes.find_many(
            {"status": NodeStatus.ACTIVE.value},
            limit=1000,
        )
        return [NodeModel.from_dict(d) for d in docs]
    
    async def update_node(self, id: str, update: Dict[str, Any]) -> bool:
        """Update node."""
        return await self._nodes.update_one(id, update)
    
    async def update_node_heartbeat(
        self,
        id: str,
        load: float,
        documents_count: int,
    ):
        """Update node heartbeat info."""
        await self.update_node(id, {
            "last_heartbeat": datetime.now(),
            "load": load,
            "documents_count": documents_count,
        })
    
    async def delete_node(self, id: str) -> bool:
        """Delete node."""
        return await self._nodes.delete_one(id)
    
    # Partition operations
    
    async def create_partition(self, partition: PartitionModel) -> str:
        """Create a new partition."""
        return await self._partitions.insert_one(partition.to_dict())
    
    async def get_partition(self, id: str) -> Optional[PartitionModel]:
        """Get partition by ID."""
        data = await self._partitions.find_by_id(id)
        return PartitionModel.from_dict(data) if data else None
    
    async def get_all_partitions(self) -> List[PartitionModel]:
        """Get all partitions."""
        docs = await self._partitions.find_many({}, limit=1000)
        return [PartitionModel.from_dict(d) for d in docs]
    
    async def get_partitions_by_node(self, node_id: str) -> List[PartitionModel]:
        """Get partitions assigned to a node."""
        docs = await self._partitions.find_many(
            {"primary_node_id": node_id},
            limit=1000,
        )
        return [PartitionModel.from_dict(d) for d in docs]
    
    async def update_partition(self, id: str, update: Dict[str, Any]) -> bool:
        """Update partition."""
        return await self._partitions.update_one(id, update)
    
    async def delete_partition(self, id: str) -> bool:
        """Delete partition."""
        return await self._partitions.delete_one(id)


class NodeRepository(BaseRepository[NodeModel]):
    """
    Repository for node operations.
    
    Provides direct access to node CRUD operations.
    """
    
    def __init__(self, client: MongoDBClient):
        super().__init__(client, "nodes")
    
    async def ensure_indexes(self):
        """Ensure indexes exist for the nodes collection."""
        await self.collection.create_indexes([
            IndexModel([("address", ASCENDING)], unique=True),
            IndexModel([("role", ASCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ])
    
    async def create(self, node: NodeModel) -> str:
        """Create a new node."""
        try:
            return await self.insert_one(node.to_dict())
        except DuplicateKeyError:
            logger.warning(f"Node {node.id} already exists")
            return node.id
    
    async def get(self, id: str) -> Optional[NodeModel]:
        """Get node by ID."""
        data = await self.find_by_id(id)
        return NodeModel.from_dict(data) if data else None
    
    async def get_by_address(self, address: str) -> Optional[NodeModel]:
        """Get node by address."""
        docs = await self.find_many({"address": address}, limit=1)
        return NodeModel.from_dict(docs[0]) if docs else None
    
    async def get_all(self) -> List[NodeModel]:
        """Get all nodes."""
        docs = await self.find_many({}, limit=1000)
        return [NodeModel.from_dict(d) for d in docs]
    
    async def get_active(self) -> List[NodeModel]:
        """Get all active nodes."""
        docs = await self.find_many(
            {"status": NodeStatus.ACTIVE.value},
            limit=1000,
        )
        return [NodeModel.from_dict(d) for d in docs]
    
    async def update(self, id: str, update: Dict[str, Any]) -> bool:
        """Update node."""
        return await self.update_one(id, update)
    
    async def update_heartbeat(
        self,
        id: str,
        load: float,
        documents_count: int,
    ):
        """Update node heartbeat info."""
        await self.update(id, {
            "last_heartbeat": datetime.now(),
            "load": load,
            "documents_count": documents_count,
        })
    
    async def delete(self, id: str) -> bool:
        """Delete node."""
        return await self.delete_one(id)
    
    async def count_active(self) -> int:
        """Count active nodes."""
        return await self.count({"status": NodeStatus.ACTIVE.value})


class MetricsRepository(BaseRepository[MetricsModel]):
    """Repository for metrics operations."""
    
    def __init__(self, client: MongoDBClient):
        super().__init__(client, "metrics")
    
    async def record_metric(
        self,
        node_id: str,
        metric_type: str,
        value: float,
        values: Optional[Dict[str, float]] = None,
    ):
        """Record a metric."""
        metric = MetricsModel(
            node_id=node_id,
            metric_type=metric_type,
            value=value,
            values=values or {},
        )
        await self.insert_one(metric.to_dict())
    
    async def get_metrics(
        self,
        node_id: str,
        metric_type: str,
        since: datetime,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get metrics for a node since a timestamp."""
        return await self.find_many(
            {
                "node_id": node_id,
                "metric_type": metric_type,
                "timestamp": {"$gte": since},
            },
            limit=limit,
            sort=[("timestamp", DESCENDING)],
        )
    
    async def get_latest_metric(
        self,
        node_id: str,
        metric_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Get latest metric for a node."""
        metrics = await self.get_metrics(node_id, metric_type, datetime.min, 1)
        return metrics[0] if metrics else None
    
    async def record_search_query(self, query: SearchQueryModel):
        """Record a search query."""
        queries = self.client.get_collection("search_queries")
        await queries.insert_one(query.to_dict())
    
    async def get_search_stats(
        self,
        since: datetime,
    ) -> Dict[str, Any]:
        """Get search statistics."""
        queries = self.client.get_collection("search_queries")
        
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_queries": {"$sum": 1},
                "avg_time_ms": {"$avg": "$query_time_ms"},
                "total_results": {"$sum": "$total_results"},
            }},
        ]
        
        result = await queries.aggregate(pipeline).to_list(length=1)
        return result[0] if result else {
            "total_queries": 0,
            "avg_time_ms": 0,
            "total_results": 0,
        }


class SearchHistoryRepository:
    """
    Repository for search history operations.
    
    Tracks search queries and their results for analytics.
    """
    
    def __init__(self, client: MongoDBClient):
        self.client = client
        self.collection_name = "search_history"
    
    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Get collection."""
        return self.client.get_collection(self.collection_name)
    
    async def ensure_indexes(self):
        """Ensure indexes exist for the search history collection."""
        await self.collection.create_indexes([
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("query", TEXT)]),
        ])
    
    async def record_search(
        self,
        query: str,
        user_id: Optional[str] = None,
        results_count: int = 0,
        response_time_ms: float = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a search query."""
        document = {
            "query": query,
            "user_id": user_id,
            "results_count": results_count,
            "response_time_ms": response_time_ms,
            "filters": filters or {},
            "created_at": datetime.now(),
        }
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)
    
    async def get_recent_searches(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent searches, optionally for a specific user."""
        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id
        
        cursor = self.collection.find(filter_query).sort(
            "created_at", DESCENDING
        ).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_popular_queries(
        self,
        since: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get most popular search queries."""
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": "$query",
                "count": {"$sum": 1},
                "avg_results": {"$avg": "$results_count"},
                "avg_time_ms": {"$avg": "$response_time_ms"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        
        return await self.collection.aggregate(pipeline).to_list(length=limit)
    
    async def get_search_stats(
        self,
        since: datetime,
    ) -> Dict[str, Any]:
        """Get search statistics."""
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_searches": {"$sum": 1},
                "avg_response_time_ms": {"$avg": "$response_time_ms"},
                "avg_results_count": {"$avg": "$results_count"},
                "unique_users": {"$addToSet": "$user_id"},
            }},
        ]
        
        result = await self.collection.aggregate(pipeline).to_list(length=1)
        
        if result:
            stats = result[0]
            stats["unique_users_count"] = len([u for u in stats.get("unique_users", []) if u])
            del stats["unique_users"]
            return stats
        
        return {
            "total_searches": 0,
            "avg_response_time_ms": 0,
            "avg_results_count": 0,
            "unique_users_count": 0,
        }

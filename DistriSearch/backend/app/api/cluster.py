"""
Cluster API Router
Endpoints for cluster management and monitoring in DistriSearch
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
import logging
import os

from .schemas import (
    NodeInfo,
    NodeStatus,
    NodeRole,
    ClusterStatus,
    PartitionInfo,
    ClusterPartitions,
    NodeJoinRequest,
    NodeJoinResponse,
    RebalanceRequest,
    RebalanceResponse,
    ErrorResponse
)
from .dependencies import (
    get_cluster_manager,
    get_node_repository,
    get_cluster_repository,
    verify_master_node,
    get_current_node
)
from ..storage.mongodb import NodeRepository, ClusterRepository
from ..distributed.coordination import ClusterManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cluster", tags=["cluster"])


@router.get(
    "/status",
    response_model=ClusterStatus,
    summary="Get cluster status",
    responses={
        200: {"description": "Cluster status information"},
        503: {"model": ErrorResponse, "description": "Cluster not available"}
    }
)
async def get_cluster_status(
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    node_repo: NodeRepository = Depends(get_node_repository)
):
    """
    Get the current status of the distributed cluster.
    
    Returns information about:
    - Master node
    - All cluster nodes and their health
    - Total documents and partitions
    - Replication factor
    """
    try:
        # Get cluster info from manager
        cluster_info = await cluster_manager.get_cluster_status()
        
        # Get all nodes from database
        nodes_data = await node_repo.find(filters={}, skip=0, limit=100)
        
        nodes = []
        healthy_count = 0
        unhealthy_count = 0
        total_documents = 0
        total_partitions = 0
        
        for node in nodes_data:
            node_status = NodeStatus(node.get("status", "unknown"))
            if node_status == NodeStatus.HEALTHY:
                healthy_count += 1
            else:
                unhealthy_count += 1
            
            total_documents += node.get("document_count", 0)
            total_partitions += node.get("partition_count", 0)
            
            nodes.append(NodeInfo(
                node_id=str(node["_id"]),
                address=node.get("address", ""),
                port=node.get("port", 8000),
                role=NodeRole(node.get("role", "slave")),
                status=node_status,
                document_count=node.get("document_count", 0),
                partition_count=node.get("partition_count", 0),
                cpu_usage=node.get("cpu_usage", 0.0),
                memory_usage=node.get("memory_usage", 0.0),
                disk_usage=node.get("disk_usage", 0.0),
                last_heartbeat=node.get("last_heartbeat"),
                joined_at=node.get("joined_at", datetime.utcnow()),
                metadata=node.get("metadata", {})
            ))
        
        # Determine overall cluster status
        if unhealthy_count == 0:
            overall_status = NodeStatus.HEALTHY
        elif healthy_count > unhealthy_count:
            overall_status = NodeStatus.DEGRADED
        else:
            overall_status = NodeStatus.UNHEALTHY
        
        return ClusterStatus(
            cluster_id=cluster_info.get("cluster_id", "distrisearch-cluster"),
            master_node_id=cluster_info.get("master_node_id"),
            master_address=cluster_info.get("master_address"),
            total_nodes=len(nodes),
            healthy_nodes=healthy_count,
            unhealthy_nodes=unhealthy_count,
            total_documents=total_documents,
            total_partitions=total_partitions,
            replication_factor=cluster_info.get("replication_factor", 2),
            status=overall_status,
            nodes=nodes,
            last_rebalance=cluster_info.get("last_rebalance"),
            created_at=cluster_info.get("created_at", datetime.utcnow())
        )
        
    except Exception as e:
        logger.error(f"Error getting cluster status: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get cluster status: {str(e)}"
        )


@router.get(
    "/nodes",
    response_model=List[NodeInfo],
    summary="List cluster nodes",
    responses={
        200: {"description": "List of cluster nodes"}
    }
)
async def list_nodes(
    status_filter: Optional[NodeStatus] = Query(default=None, description="Filter by status"),
    role_filter: Optional[NodeRole] = Query(default=None, description="Filter by role"),
    node_repo: NodeRepository = Depends(get_node_repository)
):
    """
    List all nodes in the cluster with optional filtering.
    """
    try:
        filters = {}
        if status_filter:
            filters["status"] = status_filter.value
        if role_filter:
            filters["role"] = role_filter.value
        
        nodes_data = await node_repo.find(filters=filters, skip=0, limit=100)
        
        nodes = []
        for node in nodes_data:
            nodes.append(NodeInfo(
                node_id=str(node["_id"]),
                address=node.get("address", ""),
                port=node.get("port", 8000),
                role=NodeRole(node.get("role", "slave")),
                status=NodeStatus(node.get("status", "unknown")),
                document_count=node.get("document_count", 0),
                partition_count=node.get("partition_count", 0),
                cpu_usage=node.get("cpu_usage", 0.0),
                memory_usage=node.get("memory_usage", 0.0),
                disk_usage=node.get("disk_usage", 0.0),
                last_heartbeat=node.get("last_heartbeat"),
                joined_at=node.get("joined_at", datetime.utcnow()),
                metadata=node.get("metadata", {})
            ))
        
        return nodes
        
    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list nodes: {str(e)}"
        )


@router.get(
    "/nodes/{node_id}",
    response_model=NodeInfo,
    summary="Get node details",
    responses={
        200: {"description": "Node information"},
        404: {"model": ErrorResponse, "description": "Node not found"}
    }
)
async def get_node(
    node_id: str,
    node_repo: NodeRepository = Depends(get_node_repository)
):
    """
    Get detailed information about a specific node.
    """
    try:
        node = await node_repo.find_by_id(node_id)
        
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node not found: {node_id}"
            )
        
        return NodeInfo(
            node_id=str(node["_id"]),
            address=node.get("address", ""),
            port=node.get("port", 8000),
            role=NodeRole(node.get("role", "slave")),
            status=NodeStatus(node.get("status", "unknown")),
            document_count=node.get("document_count", 0),
            partition_count=node.get("partition_count", 0),
            cpu_usage=node.get("cpu_usage", 0.0),
            memory_usage=node.get("memory_usage", 0.0),
            disk_usage=node.get("disk_usage", 0.0),
            last_heartbeat=node.get("last_heartbeat"),
            joined_at=node.get("joined_at", datetime.utcnow()),
            metadata=node.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get node: {str(e)}"
        )


@router.post(
    "/nodes/join",
    response_model=NodeJoinResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join the cluster",
    responses={
        201: {"description": "Successfully joined cluster"},
        400: {"model": ErrorResponse, "description": "Invalid join request"},
        409: {"model": ErrorResponse, "description": "Node already in cluster"}
    }
)
async def join_cluster(
    request: NodeJoinRequest,
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    node_repo: NodeRepository = Depends(get_node_repository)
):
    """
    Request to join the cluster as a new node.
    
    This endpoint is called by slave nodes when they start up
    to register with the cluster.
    """
    try:
        # Check if node already exists
        existing = await node_repo.find_by_id(request.node_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Node already registered: {request.node_id}"
            )
        
        # Register the node
        result = await cluster_manager.register_node(
            node_id=request.node_id,
            address=request.address,
            port=request.port,
            capabilities=request.capabilities
        )
        
        # Store node in database
        await node_repo.create({
            "_id": request.node_id,
            "address": request.address,
            "port": request.port,
            "role": "slave",
            "status": "healthy",
            "document_count": 0,
            "partition_count": 0,
            "capabilities": request.capabilities,
            "joined_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow()
        })
        
        logger.info(f"Node joined cluster: {request.node_id}")
        
        return NodeJoinResponse(
            success=True,
            message="Successfully joined cluster",
            cluster_id=result.get("cluster_id", "distrisearch-cluster"),
            master_node_id=result.get("master_node_id", ""),
            assigned_partitions=result.get("assigned_partitions", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to join cluster: {str(e)}"
        )


@router.delete(
    "/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove node from cluster",
    dependencies=[Depends(verify_master_node)],
    responses={
        204: {"description": "Node removed"},
        404: {"model": ErrorResponse, "description": "Node not found"}
    }
)
async def remove_node(
    node_id: str,
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    node_repo: NodeRepository = Depends(get_node_repository),
    current_node: dict = Depends(get_current_node)
):
    """
    Remove a node from the cluster (master only).
    
    This will trigger:
    1. Data migration from the removed node
    2. Partition reassignment
    3. Replica rebalancing
    """
    try:
        if node_id == current_node["node_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the current node"
            )
        
        node = await node_repo.find_by_id(node_id)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node not found: {node_id}"
            )
        
        # Trigger graceful removal
        await cluster_manager.remove_node(node_id)
        
        # Remove from database
        await node_repo.delete(node_id)
        
        logger.info(f"Node removed from cluster: {node_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove node: {str(e)}"
        )


@router.get(
    "/partitions",
    response_model=ClusterPartitions,
    summary="List partitions",
    responses={
        200: {"description": "Partition information"}
    }
)
async def list_partitions(
    node_id: Optional[str] = Query(default=None, description="Filter by node"),
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    List all partitions in the cluster.
    """
    try:
        partitions_data = await cluster_manager.get_partitions(node_id=node_id)
        
        partitions = []
        for p in partitions_data.get("partitions", []):
            partitions.append(PartitionInfo(
                partition_id=p["partition_id"],
                primary_node_id=p.get("primary_node_id", ""),
                replica_node_ids=p.get("replica_node_ids", []),
                document_count=p.get("document_count", 0),
                size_bytes=p.get("size_bytes", 0),
                status=p.get("status", "active"),
                created_at=p.get("created_at", datetime.utcnow()),
                last_modified=p.get("last_modified", datetime.utcnow())
            ))
        
        return ClusterPartitions(
            total_partitions=len(partitions),
            partitions=partitions,
            replication_factor=partitions_data.get("replication_factor", 2)
        )
        
    except Exception as e:
        logger.error(f"Error listing partitions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list partitions: {str(e)}"
        )


@router.post(
    "/rebalance",
    response_model=RebalanceResponse,
    summary="Trigger cluster rebalance",
    dependencies=[Depends(verify_master_node)],
    responses={
        200: {"description": "Rebalance initiated"},
        409: {"model": ErrorResponse, "description": "Rebalance already in progress"}
    }
)
async def trigger_rebalance(
    request: RebalanceRequest,
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Trigger a cluster rebalance operation (master only).
    
    This will:
    1. Analyze current data distribution
    2. Plan migrations to balance load
    3. Execute migrations with minimal disruption
    """
    try:
        result = await cluster_manager.trigger_rebalance(
            force=request.force,
            target_node_id=request.target_node_id
        )
        
        if not result.get("success"):
            if result.get("reason") == "already_in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Rebalance operation already in progress"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("reason", "Rebalance failed")
            )
        
        logger.info(f"Rebalance triggered: {result}")
        
        return RebalanceResponse(
            success=True,
            message="Rebalance operation initiated",
            migrations_planned=result.get("migrations_planned", 0),
            estimated_time_seconds=result.get("estimated_time", 0.0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering rebalance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger rebalance: {str(e)}"
        )


@router.get(
    "/master",
    response_model=NodeInfo,
    summary="Get master node",
    responses={
        200: {"description": "Master node information"},
        404: {"model": ErrorResponse, "description": "No master elected"}
    }
)
async def get_master_node(
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    node_repo: NodeRepository = Depends(get_node_repository)
):
    """
    Get information about the current master node.
    """
    try:
        master_id = await cluster_manager.get_master_node_id()
        
        if not master_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No master node currently elected"
            )
        
        node = await node_repo.find_by_id(master_id)
        
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Master node not found: {master_id}"
            )
        
        return NodeInfo(
            node_id=str(node["_id"]),
            address=node.get("address", ""),
            port=node.get("port", 8000),
            role=NodeRole.MASTER,
            status=NodeStatus(node.get("status", "unknown")),
            document_count=node.get("document_count", 0),
            partition_count=node.get("partition_count", 0),
            cpu_usage=node.get("cpu_usage", 0.0),
            memory_usage=node.get("memory_usage", 0.0),
            disk_usage=node.get("disk_usage", 0.0),
            last_heartbeat=node.get("last_heartbeat"),
            joined_at=node.get("joined_at", datetime.utcnow()),
            metadata=node.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting master node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get master node: {str(e)}"
        )


@router.post(
    "/election",
    summary="Trigger master election",
    dependencies=[Depends(verify_master_node)],
    responses={
        200: {"description": "Election triggered"},
        409: {"model": ErrorResponse, "description": "Election already in progress"}
    }
)
async def trigger_election(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Manually trigger a master election (for testing/maintenance).
    """
    try:
        result = await cluster_manager.trigger_election()
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Election triggered"),
            "new_master": result.get("new_master")
        }
        
    except Exception as e:
        logger.error(f"Error triggering election: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger election: {str(e)}"
        )

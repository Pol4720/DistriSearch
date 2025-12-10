"""
Health Check API Router
Health, readiness, and liveness endpoints for DistriSearch
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
import logging
import time
import os
import psutil

from .schemas import (
    HealthStatus,
    HealthResponse,
    ReadinessResponse,
    LivenessResponse,
    ComponentHealth,
    NodeRole
)
from .dependencies import (
    get_db,
    get_cluster_manager,
    get_current_node,
    _mongodb_client
)
from ..distributed.coordination import ClusterManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time
_start_time = time.time()
_version = os.getenv("APP_VERSION", "1.0.0")


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"}
    }
)
async def health_check(
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node)
):
    """
    Comprehensive health check of the DistriSearch service.
    
    Checks the health of:
    - Database connection
    - Cluster connectivity
    - System resources (CPU, memory, disk)
    """
    components = []
    overall_status = HealthStatus.HEALTHY
    
    # Check MongoDB
    db_health = await _check_mongodb_health()
    components.append(db_health)
    if db_health.status != HealthStatus.HEALTHY:
        overall_status = HealthStatus.DEGRADED
    
    # Check cluster connectivity
    cluster_health = await _check_cluster_health(cluster_manager)
    components.append(cluster_health)
    if cluster_health.status == HealthStatus.UNHEALTHY:
        overall_status = HealthStatus.UNHEALTHY
    elif cluster_health.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
        overall_status = HealthStatus.DEGRADED
    
    # Check system resources
    system_health = _check_system_resources()
    components.append(system_health)
    if system_health.status != HealthStatus.HEALTHY:
        if overall_status == HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED
    
    # Check disk space
    disk_health = _check_disk_health()
    components.append(disk_health)
    if disk_health.status == HealthStatus.UNHEALTHY:
        overall_status = HealthStatus.UNHEALTHY
    elif disk_health.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
        overall_status = HealthStatus.DEGRADED
    
    uptime = time.time() - _start_time
    
    response = HealthResponse(
        status=overall_status,
        node_id=current_node["node_id"],
        role=NodeRole(current_node.get("role", "slave")),
        version=_version,
        uptime_seconds=uptime,
        components=components,
        timestamp=datetime.utcnow()
    )
    
    # Return 503 if unhealthy
    if overall_status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    
    return response


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"}
    }
)
async def readiness_check(
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Kubernetes-style readiness check.
    
    The service is ready when:
    - Database is connected
    - Cluster is initialized
    - Node is registered
    """
    checks = {}
    all_ready = True
    
    # Check database connection
    try:
        if _mongodb_client and _mongodb_client.client:
            await _mongodb_client.client.admin.command('ping')
            checks["database"] = True
        else:
            checks["database"] = False
            all_ready = False
    except Exception:
        checks["database"] = False
        all_ready = False
    
    # Check cluster initialization
    try:
        checks["cluster_initialized"] = cluster_manager.is_initialized
        if not cluster_manager.is_initialized:
            all_ready = False
    except Exception:
        checks["cluster_initialized"] = False
        all_ready = False
    
    # Check node registration
    try:
        checks["node_registered"] = cluster_manager.is_registered
        if not cluster_manager.is_registered:
            all_ready = False
    except Exception:
        checks["node_registered"] = False
        all_ready = False
    
    response = ReadinessResponse(
        ready=all_ready,
        message="Service is ready" if all_ready else "Service is not ready",
        checks=checks
    )
    
    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    
    return response


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness check",
    responses={
        200: {"description": "Service is alive"}
    }
)
async def liveness_check():
    """
    Kubernetes-style liveness check.
    
    Simple check to verify the service process is running and responsive.
    """
    return LivenessResponse(
        alive=True,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/metrics",
    summary="Get service metrics",
    responses={
        200: {"description": "Service metrics"}
    }
)
async def get_metrics(
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node)
):
    """
    Get detailed metrics for monitoring and observability.
    """
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        
        # Cluster metrics
        cluster_stats = await cluster_manager.get_cluster_stats()
        
        return {
            "node_id": current_node["node_id"],
            "role": current_node.get("role", "slave"),
            "uptime_seconds": time.time() - _start_time,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_total_bytes": memory.total,
                "memory_available_bytes": memory.available,
                "memory_percent": memory.percent,
                "disk_total_bytes": disk.total,
                "disk_free_bytes": disk.free,
                "disk_percent": disk.percent
            },
            "process": {
                "memory_rss_bytes": process_memory.rss,
                "memory_vms_bytes": process_memory.vms,
                "threads": process.num_threads(),
                "open_files": len(process.open_files())
            },
            "cluster": {
                "total_nodes": cluster_stats.get("total_nodes", 0),
                "healthy_nodes": cluster_stats.get("healthy_nodes", 0),
                "total_documents": cluster_stats.get("total_documents", 0),
                "total_partitions": cluster_stats.get("total_partitions", 0),
                "is_master": cluster_manager.is_master
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}"
        )


async def _check_mongodb_health() -> ComponentHealth:
    """Check MongoDB connection health"""
    try:
        if _mongodb_client and _mongodb_client.client:
            start = time.time()
            await _mongodb_client.client.admin.command('ping')
            latency = (time.time() - start) * 1000
            
            if latency < 100:
                return ComponentHealth(
                    name="mongodb",
                    status=HealthStatus.HEALTHY,
                    message="Connected",
                    latency_ms=latency
                )
            else:
                return ComponentHealth(
                    name="mongodb",
                    status=HealthStatus.DEGRADED,
                    message=f"High latency: {latency:.2f}ms",
                    latency_ms=latency
                )
        else:
            return ComponentHealth(
                name="mongodb",
                status=HealthStatus.UNHEALTHY,
                message="Not connected"
            )
    except Exception as e:
        return ComponentHealth(
            name="mongodb",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def _check_cluster_health(cluster_manager: ClusterManager) -> ComponentHealth:
    """Check cluster connectivity health"""
    try:
        if not cluster_manager.is_initialized:
            return ComponentHealth(
                name="cluster",
                status=HealthStatus.DEGRADED,
                message="Cluster not initialized"
            )
        
        stats = await cluster_manager.get_cluster_stats()
        healthy_ratio = stats.get("healthy_nodes", 0) / max(stats.get("total_nodes", 1), 1)
        
        if healthy_ratio >= 0.8:
            return ComponentHealth(
                name="cluster",
                status=HealthStatus.HEALTHY,
                message=f"{stats.get('healthy_nodes', 0)}/{stats.get('total_nodes', 0)} nodes healthy"
            )
        elif healthy_ratio >= 0.5:
            return ComponentHealth(
                name="cluster",
                status=HealthStatus.DEGRADED,
                message=f"Only {stats.get('healthy_nodes', 0)}/{stats.get('total_nodes', 0)} nodes healthy"
            )
        else:
            return ComponentHealth(
                name="cluster",
                status=HealthStatus.UNHEALTHY,
                message=f"Critical: {stats.get('healthy_nodes', 0)}/{stats.get('total_nodes', 0)} nodes healthy"
            )
    except Exception as e:
        return ComponentHealth(
            name="cluster",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


def _check_system_resources() -> ComponentHealth:
    """Check system resources health"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        if cpu_percent < 80 and memory.percent < 80:
            return ComponentHealth(
                name="system",
                status=HealthStatus.HEALTHY,
                message=f"CPU: {cpu_percent}%, Memory: {memory.percent}%"
            )
        elif cpu_percent < 95 and memory.percent < 95:
            return ComponentHealth(
                name="system",
                status=HealthStatus.DEGRADED,
                message=f"High usage - CPU: {cpu_percent}%, Memory: {memory.percent}%"
            )
        else:
            return ComponentHealth(
                name="system",
                status=HealthStatus.UNHEALTHY,
                message=f"Critical - CPU: {cpu_percent}%, Memory: {memory.percent}%"
            )
    except Exception as e:
        return ComponentHealth(
            name="system",
            status=HealthStatus.DEGRADED,
            message=f"Unable to check: {str(e)}"
        )


def _check_disk_health() -> ComponentHealth:
    """Check disk space health"""
    try:
        disk = psutil.disk_usage('/')
        
        if disk.percent < 80:
            return ComponentHealth(
                name="disk",
                status=HealthStatus.HEALTHY,
                message=f"{disk.percent}% used"
            )
        elif disk.percent < 95:
            return ComponentHealth(
                name="disk",
                status=HealthStatus.DEGRADED,
                message=f"Low space: {disk.percent}% used"
            )
        else:
            return ComponentHealth(
                name="disk",
                status=HealthStatus.UNHEALTHY,
                message=f"Critical: {disk.percent}% used"
            )
    except Exception as e:
        return ComponentHealth(
            name="disk",
            status=HealthStatus.DEGRADED,
            message=f"Unable to check: {str(e)}"
        )

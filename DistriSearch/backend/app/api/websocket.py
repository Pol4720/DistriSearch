"""
WebSocket API Router
WebSocket endpoints for real-time updates in DistriSearch
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional, Set, Dict
from datetime import datetime
import logging
import json
import asyncio

from .schemas import (
    WSMessage,
    WSMessageType,
    ClusterStatus,
    NodeStatus,
    NodeInfo
)
from .dependencies import (
    get_cluster_manager,
    get_node_repository
)
from ..distributed.coordination import ClusterManager
from ..distributed.communication import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Global WebSocket manager
ws_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(default=None)
):
    """
    Main WebSocket endpoint for real-time updates.
    
    Clients can receive:
    - Cluster status updates
    - Node status changes
    - Search progress
    - Rebalance progress
    """
    await ws_manager.connect(websocket, client_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id or ws_manager.get_connection_id(websocket),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Subscribe to specific topics
                topics = data.get("topics", [])
                await ws_manager.subscribe(websocket, topics)
                await websocket.send_json({
                    "type": "subscribed",
                    "topics": topics,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            elif message_type == "unsubscribe":
                # Unsubscribe from topics
                topics = data.get("topics", [])
                await ws_manager.unsubscribe(websocket, topics)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "topics": topics,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            elif message_type == "get_status":
                # Request current status
                await _send_cluster_status(websocket)
                
            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/cluster")
async def websocket_cluster_updates(websocket: WebSocket):
    """
    WebSocket endpoint for cluster status updates.
    
    Automatically sends cluster status updates every 5 seconds.
    """
    await ws_manager.connect(websocket, subscription_topics=["cluster"])
    
    try:
        # Start background task to send periodic updates
        update_task = asyncio.create_task(
            _cluster_update_loop(websocket)
        )
        
        while True:
            # Keep connection alive, handle any incoming messages
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Cluster WebSocket error: {e}")
    finally:
        update_task.cancel()
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/search/{query_id}")
async def websocket_search_progress(
    websocket: WebSocket,
    query_id: str
):
    """
    WebSocket endpoint for search progress updates.
    
    Connects to a specific search query and receives real-time progress.
    """
    await ws_manager.connect(websocket, subscription_topics=[f"search:{query_id}"])
    
    try:
        await websocket.send_json({
            "type": "connected",
            "query_id": query_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "cancel":
                # Request to cancel search
                await _cancel_search(query_id)
                await websocket.send_json({
                    "type": "cancelled",
                    "query_id": query_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Search WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket)


async def _cluster_update_loop(websocket: WebSocket, interval: float = 5.0):
    """Background loop to send cluster updates"""
    try:
        while True:
            await _send_cluster_status(websocket)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Cluster update loop error: {e}")


async def _send_cluster_status(websocket: WebSocket):
    """Send current cluster status to websocket"""
    try:
        # Get cluster manager (would need to be passed differently in production)
        from .dependencies import _cluster_manager, _node_repository
        
        if not _cluster_manager:
            await websocket.send_json({
                "type": WSMessageType.ERROR.value,
                "message": "Cluster manager not initialized",
                "timestamp": datetime.utcnow().isoformat()
            })
            return
        
        cluster_info = await _cluster_manager.get_cluster_status()
        
        await websocket.send_json({
            "type": WSMessageType.CLUSTER_UPDATE.value,
            "data": {
                "cluster_id": cluster_info.get("cluster_id", "distrisearch-cluster"),
                "master_node_id": cluster_info.get("master_node_id"),
                "total_nodes": cluster_info.get("total_nodes", 0),
                "healthy_nodes": cluster_info.get("healthy_nodes", 0),
                "total_documents": cluster_info.get("total_documents", 0),
                "status": cluster_info.get("status", "unknown")
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error sending cluster status: {e}")


async def _cancel_search(query_id: str):
    """Cancel a running search query"""
    try:
        from .dependencies import _search_engine
        
        if _search_engine:
            await _search_engine.cancel_query(query_id)
            logger.info(f"Search cancelled: {query_id}")
    except Exception as e:
        logger.error(f"Error cancelling search: {e}")


# Broadcast functions for use by other modules

async def broadcast_cluster_update(cluster_status: dict):
    """Broadcast cluster status update to all subscribed clients"""
    message = {
        "type": WSMessageType.CLUSTER_UPDATE.value,
        "data": cluster_status,
        "timestamp": datetime.utcnow().isoformat()
    }
    await ws_manager.broadcast(message, topic="cluster")


async def broadcast_node_status(node_id: str, status: str, metrics: dict = None):
    """Broadcast node status change"""
    message = {
        "type": WSMessageType.NODE_STATUS.value,
        "data": {
            "node_id": node_id,
            "status": status,
            "metrics": metrics or {}
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    await ws_manager.broadcast(message, topic="cluster")


async def broadcast_search_progress(query_id: str, progress: dict):
    """Broadcast search progress update"""
    message = {
        "type": WSMessageType.SEARCH_PROGRESS.value,
        "data": progress,
        "timestamp": datetime.utcnow().isoformat()
    }
    await ws_manager.broadcast(message, topic=f"search:{query_id}")


async def broadcast_rebalance_progress(progress: dict):
    """Broadcast rebalance progress update"""
    message = {
        "type": WSMessageType.REBALANCE_PROGRESS.value,
        "data": progress,
        "timestamp": datetime.utcnow().isoformat()
    }
    await ws_manager.broadcast(message, topic="cluster")


# Connection info endpoints

@router.get("/ws/connections", tags=["websocket"])
async def get_websocket_connections():
    """
    Get information about active WebSocket connections.
    """
    return {
        "total_connections": ws_manager.connection_count,
        "subscriptions": ws_manager.get_subscription_stats()
    }

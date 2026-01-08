"""
Internal API endpoints for distributed coordination.

These endpoints are used for node-to-node communication,
including Raft consensus protocol messages.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .dependencies import get_raft_node

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/raft/status")
async def get_raft_status() -> Dict[str, Any]:
    """
    Get the current Raft status of this node.
    
    Returns:
        - node_id: The ID of this node
        - state: Current state (follower, candidate, leader)
        - term: Current term number
        - leader_id: The ID of the current leader (if known)
        - peers: List of known peer node IDs
        - voted_for: Who this node voted for in current term
    """
    raft_node = await get_raft_node()
    
    if raft_node is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raft node not initialized"
        )
    
    return {
        "node_id": raft_node.node_id,
        "role": raft_node.state.role.value if hasattr(raft_node.state.role, 'value') else str(raft_node.state.role),
        "term": raft_node.state.current_term,
        "leader_id": raft_node.state.leader_id,
        "peers": list(raft_node.state.cluster_nodes.keys()),
        "voted_for": raft_node.state.persistent.voted_for,
        "commit_index": raft_node.state.volatile.commit_index,
    }


class RaftRPCRequest(BaseModel):
    """Request model for Raft RPC calls."""
    type: str  # "request_vote", "append_entries", etc.
    data: Dict[str, Any]  # The actual RPC data


@router.post("/raft")
async def handle_raft_rpc(request: RaftRPCRequest) -> Dict[str, Any]:
    """
    Handle incoming Raft RPC messages.
    
    This endpoint processes:
    - RequestVote: For leader election
    - AppendEntries: For log replication and heartbeats
    """
    raft_node = await get_raft_node()
    
    if raft_node is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raft node not initialized"
        )
    
    logger.debug(f"Received Raft RPC: type={request.type}")
    
    try:
        data = request.data
        
        if request.type == "request_vote":
            # Handle RequestVote RPC
            result = await raft_node.handle_request_vote(args=data)
            return {
                "term": result.term,
                "vote_granted": result.vote_granted,
            }
            
        elif request.type == "append_entries":
            # Handle AppendEntries RPC
            result = await raft_node.handle_append_entries(args=data)
            return {
                "term": result.term,
                "success": result.success,
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown RPC type: {request.type}"
            )
            
    except Exception as e:
        logger.error(f"Error handling Raft RPC: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Raft RPC: {str(e)}"
        )
        logger.error(f"Error handling Raft RPC: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Raft RPC: {str(e)}"
        )

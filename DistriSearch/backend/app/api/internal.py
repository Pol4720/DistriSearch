"""
Internal API endpoints for distributed coordination.

These endpoints are used for node-to-node communication,
including Raft consensus protocol messages and Bully election.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .dependencies import get_raft_node, get_bully_election

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


# =============================================================================
# Bully Election Endpoints
# =============================================================================

@router.post("/bully")
async def handle_bully_message(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle incoming Bully election messages.
    
    This endpoint processes:
    - ELECTION: A node is starting an election
    - OK: Response to election from higher priority node
    - COORDINATOR: Announcement of new leader
    - HEARTBEAT: Leader heartbeat
    """
    bully = await get_bully_election()
    
    if bully is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bully election not initialized"
        )
    
    try:
        result = await bully.handle_message(request)
        return result
    except Exception as e:
        logger.error(f"Error handling Bully message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Bully message: {str(e)}"
        )


@router.get("/bully/status")
async def get_bully_status() -> Dict[str, Any]:
    """
    Get the current Bully election status.
    
    Returns:
        - node_id: This node's ID
        - is_leader: Whether this node is the leader
        - leader_id: The current leader's ID
        - peers: List of known peer IDs
    """
    bully = await get_bully_election()
    
    if bully is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bully election not initialized"
        )
    
    return bully.get_status()


@router.post("/bully/election")
async def trigger_election() -> Dict[str, Any]:
    """Manually trigger a new election."""
    bully = await get_bully_election()
    
    if bully is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bully election not initialized"
        )
    
    await bully.start_election()
    return {"status": "election_started", "node_id": bully.node_id}


# =============================================================================
# User Synchronization Endpoints
# =============================================================================

class SyncUserRequest(BaseModel):
    """Request to sync a user to this node."""
    id: str
    username: str
    email: str
    password_hash: str
    salt: str
    role: str = "user"
    status: str = "active"
    full_name: Optional[str] = None


@router.post("/sync/user")
async def sync_user(request: SyncUserRequest) -> Dict[str, Any]:
    """
    Sync a user from another node.
    
    This is called by other nodes to replicate user data.
    """
    from .auth import get_user_repository
    from ..storage.models import UserModel, UserStatus, UserRole
    
    try:
        user_repo = await get_user_repository()
        
        # Check if user already exists
        existing = await user_repo.find_by_email(request.email)
        if existing:
            return {"status": "already_exists", "user_id": existing.id}
        
        existing = await user_repo.find_by_username(request.username)
        if existing:
            return {"status": "already_exists", "user_id": existing.id}
        
        # Create user model directly with hashed password
        user = UserModel(
            id=request.id,
            username=request.username,
            email=request.email,
            password_hash=request.password_hash,
            salt=request.salt,
            role=request.role,
            status=UserStatus.ACTIVE,
            full_name=request.full_name,
        )
        
        # Save to local database
        created = await user_repo.create(user)
        logger.info(f"Synced user {request.username} from another node")
        
        return {"status": "synced", "user_id": created.id}
        
    except Exception as e:
        logger.error(f"Error syncing user: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/sync/users")
async def get_all_users_for_sync() -> Dict[str, Any]:
    """
    Get all users from this node for synchronization.
    
    This endpoint is used by other nodes to request all users
    from this node during initial sync.
    """
    from .auth import get_user_repository
    
    try:
        user_repo = await get_user_repository()
        users = await user_repo.list_users(skip=0, limit=10000)
        
        users_data = []
        for user in users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "password_hash": user.password_hash,
                "salt": user.salt,
                "role": user.role,
                "status": user.status.value if hasattr(user.status, 'value') else str(user.status),
                "full_name": user.full_name,
            })
        
        return {"status": "ok", "users": users_data, "count": len(users_data)}
        
    except Exception as e:
        logger.error(f"Error getting users for sync: {e}")
        return {"status": "error", "message": str(e), "users": [], "count": 0}


# =============================================================================
# Internal Search Endpoint (for distributed search)
# =============================================================================

class InternalSearchRequest(BaseModel):
    """Request for internal/local search."""
    query: str
    search_type: str = "hybrid"
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    local_only: bool = True  # Must be true to prevent recursion


@router.post("/search")
async def internal_search(request: InternalSearchRequest) -> Dict[str, Any]:
    """
    Perform local-only search on this node.
    
    This endpoint is called by other nodes during distributed search.
    It only searches the local MongoDB, never federates to other nodes.
    """
    import re
    import os
    from .dependencies import get_document_repository
    
    try:
        doc_repo = await get_document_repository()
        
        # Get all documents from local MongoDB
        all_docs = await doc_repo.find_many({}, limit=1000)
        
        # Query processing
        query_terms = [w for w in re.findall(r'\b\w+\b', request.query.lower()) if len(w) > 2]
        query_term_set = set(query_terms)
        query_lower = request.query.lower().strip()
        
        results = []
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Build corpus statistics for BM25
        doc_count = len(all_docs)
        avg_doc_length = 0
        term_doc_freq = {}
        
        doc_data_list = []
        for doc in all_docs:
            doc_dict = doc if isinstance(doc, dict) else doc.dict()
            content = doc_dict.get("content", "").lower()
            title = doc_dict.get("title", "").lower()
            full_text = title + " " + content
            
            doc_terms = [w for w in re.findall(r'\b\w+\b', full_text) if len(w) > 2]
            avg_doc_length += len(doc_terms)
            
            unique_terms = set(doc_terms)
            for term in unique_terms:
                term_doc_freq[term] = term_doc_freq.get(term, 0) + 1
            
            term_freq = {}
            for term in doc_terms:
                term_freq[term] = term_freq.get(term, 0) + 1
            
            doc_data_list.append({
                "doc_dict": doc_dict,
                "doc_terms": doc_terms,
                "term_freq": term_freq,
                "doc_length": len(doc_terms)
            })
        
        avg_doc_length = avg_doc_length / doc_count if doc_count > 0 else 1
        
        # BM25 parameters
        k1 = 1.5
        b = 0.75
        
        import math
        
        for doc_data in doc_data_list:
            doc_dict = doc_data["doc_dict"]
            doc_terms_set = set(doc_data["doc_terms"])
            matched_terms = query_term_set & doc_terms_set
            
            title_lower = doc_dict.get("title", "").lower()
            filename_lower = doc_dict.get("filename", doc_dict.get("title", "")).lower()
            
            is_substring_match = (
                query_lower in title_lower or 
                query_lower in filename_lower
            )
            
            if not matched_terms and not is_substring_match:
                continue
            
            # Calculate BM25 score
            bm25_score = 0.0
            for term in query_terms:
                if term not in doc_data["term_freq"]:
                    continue
                
                tf = doc_data["term_freq"][term]
                df = term_doc_freq.get(term, 1)
                idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)
                
                doc_length = doc_data["doc_length"]
                tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avg_doc_length)))
                bm25_score += idf * tf_component
            
            # Boost for substring match
            if is_substring_match:
                bm25_score += 5.0
            
            # Final score
            final_score = bm25_score
            
            results.append({
                "document_id": str(doc_dict.get("_id", doc_dict.get("id", ""))),
                "title": doc_dict.get("title", "Untitled"),
                "content": doc_dict.get("content", "")[:500],
                "score": final_score,
                "node_id": node_id,
                "matched_terms": list(matched_terms),
                "metadata": doc_dict.get("metadata", {})
            })
        
        # Sort by score and limit
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        results = results[:request.top_k]
        
        # Normalize scores to 0-1 range
        if results:
            max_score = max(r.get("score", 0) for r in results)
            if max_score > 1.0:
                for r in results:
                    r["score"] = round(r.get("score", 0) / max_score, 4)
        
        logger.info(f"Internal search for '{request.query}' returned {len(results)} results")
        
        return {
            "status": "ok",
            "results": results,
            "total": len(results),
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Internal search error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "results": [],
            "total": 0
        }


# =============================================================================
# Document Replication Endpoints (for distributed document management)
# =============================================================================

class ReplicateDocumentRequest(BaseModel):
    """Request to replicate a document to this node."""
    document_id: str
    source_node_id: str
    document_data: Dict[str, Any]  # Full document data including content


@router.post("/document/replicate")
async def replicate_document(request: ReplicateDocumentRequest) -> Dict[str, Any]:
    """
    Replicate a document from another node to this node.
    
    This endpoint is called by the primary node to replicate documents
    to maintain the replication factor.
    """
    import os
    from .dependencies import get_document_repository
    
    try:
        doc_repo = await get_document_repository()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Check if document already exists locally
        existing = await doc_repo.find_by_id(request.document_id)
        if existing:
            logger.info(f"Document {request.document_id} already exists on {node_id}")
            return {
                "status": "already_exists",
                "document_id": request.document_id,
                "node_id": node_id
            }
        
        # Store the document locally
        doc_data = request.document_data.copy()
        doc_data["_id"] = request.document_id
        doc_data["is_replica"] = True
        doc_data["primary_node"] = request.source_node_id
        
        await doc_repo.create(doc_data)
        
        logger.info(f"Replicated document {request.document_id} from {request.source_node_id} to {node_id}")
        
        return {
            "status": "replicated",
            "document_id": request.document_id,
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Error replicating document: {e}")
        return {
            "status": "error",
            "message": str(e),
            "document_id": request.document_id
        }


class DeleteDocumentRequest(BaseModel):
    """Request to delete a document from this node."""
    document_id: str
    propagate: bool = False  # If true, this node should also propagate to others


@router.post("/document/delete")
async def delete_document_replica(request: DeleteDocumentRequest) -> Dict[str, Any]:
    """
    Delete a document replica from this node.
    
    This endpoint is called by other nodes to propagate document deletion
    across the cluster for eventual consistency.
    """
    import os
    from .dependencies import get_document_repository
    
    try:
        doc_repo = await get_document_repository()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Check if document exists
        existing = await doc_repo.find_by_id(request.document_id)
        if not existing:
            logger.info(f"Document {request.document_id} not found on {node_id} (already deleted)")
            return {
                "status": "not_found",
                "document_id": request.document_id,
                "node_id": node_id
            }
        
        # Delete the document
        await doc_repo.delete(request.document_id)
        
        logger.info(f"Deleted document replica {request.document_id} from {node_id}")
        
        return {
            "status": "deleted",
            "document_id": request.document_id,
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Error deleting document replica: {e}")
        return {
            "status": "error",
            "message": str(e),
            "document_id": request.document_id
        }


@router.get("/document/{document_id}")
async def get_document_for_replication(document_id: str) -> Dict[str, Any]:
    """
    Get a document's full data for replication purposes.
    
    This endpoint is called by other nodes to fetch document data
    when they need to replicate a document.
    """
    import os
    from .dependencies import get_document_repository
    
    try:
        doc_repo = await get_document_repository()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            return {
                "status": "not_found",
                "document_id": document_id,
                "node_id": node_id
            }
        
        # Convert to dict if needed
        doc_data = doc if isinstance(doc, dict) else doc.dict()
        
        return {
            "status": "ok",
            "document_id": document_id,
            "node_id": node_id,
            "document_data": doc_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching document for replication: {e}")
        return {
            "status": "error",
            "message": str(e),
            "document_id": document_id
        }


class DocumentListRequest(BaseModel):
    """Request to list documents by owner"""
    owner_id: str
    tag: Optional[str] = None


@router.post("/documents/list")
async def internal_list_documents(request: DocumentListRequest) -> Dict[str, Any]:
    """
    Internal endpoint to list documents by owner.
    Used for federating document list queries across nodes.
    """
    import os
    from .dependencies import get_document_repository
    
    try:
        doc_repo = await get_document_repository()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Build filter
        filters = {"owner_id": request.owner_id}
        if request.tag:
            filters["tags"] = request.tag
        
        # Get all matching documents
        documents = await doc_repo.find(
            filters=filters,
            skip=0,
            limit=1000,
            sort=[("created_at", -1)]
        )
        
        # Convert documents to dicts
        doc_list = []
        for doc in documents:
            doc_dict = doc if isinstance(doc, dict) else doc.dict()
            # Ensure _id is string
            if "_id" in doc_dict:
                doc_dict["_id"] = str(doc_dict["_id"])
            doc_list.append(doc_dict)
        
        logger.info(f"Internal documents list for owner '{request.owner_id}' returned {len(doc_list)} documents")
        
        return {
            "status": "ok",
            "documents": doc_list,
            "total": len(doc_list),
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Internal documents list error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "documents": [],
            "total": 0
        }
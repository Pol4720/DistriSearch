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
    file_content_base64: Optional[str] = None  # Base64 encoded file content (for file replication)


@router.post("/document/replicate")
async def replicate_document(request: ReplicateDocumentRequest) -> Dict[str, Any]:
    """
    Replicate a document from another node to this node.
    
    This endpoint is called by the primary node to replicate documents
    to maintain the replication factor. If the document has an associated file,
    the file content is also replicated.
    """
    import os
    import base64
    from .dependencies import get_document_repository
    from ..storage.file_handler import FileHandler
    
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
        
        # If there's file content, save it locally
        if request.file_content_base64:
            try:
                file_content = base64.b64decode(request.file_content_base64)
                metadata = doc_data.get("metadata", {})
                filename = metadata.get("filename", f"{request.document_id}.bin")
                content_type = metadata.get("content_type", "application/octet-stream")
                
                file_handler = FileHandler()
                uploaded_file = await file_handler.save_file(
                    file_data=file_content,
                    filename=filename,
                    content_type=content_type
                )
                
                # Update file_path to local path
                if "metadata" not in doc_data:
                    doc_data["metadata"] = {}
                doc_data["metadata"]["file_path"] = uploaded_file.storage_path
                doc_data["metadata"]["replica_file"] = True
                
                logger.info(f"Replicated file for {request.document_id} to {uploaded_file.storage_path}")
            except Exception as e:
                logger.warning(f"Could not replicate file for {request.document_id}: {e}")
                # Continue without file - it can be fetched on demand
        
        await doc_repo.create(doc_data)
        
        logger.info(f"Replicated document {request.document_id} from {request.source_node_id} to {node_id}")
        
        return {
            "status": "replicated",
            "document_id": request.document_id,
            "node_id": node_id,
            "file_replicated": bool(request.file_content_base64)
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


@router.get("/document/{document_id}/file")
async def get_document_file(document_id: str):
    """
    Get a document's file content for distributed download.
    
    This endpoint is called by other nodes when they need to serve
    a file that exists on this node but not on the requesting node.
    """
    import os
    from fastapi.responses import Response
    from .dependencies import get_document_repository
    from ..storage.file_handler import FileHandler
    
    try:
        doc_repo = await get_document_repository()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            return Response(
                content=b"Document not found",
                status_code=404,
                media_type="text/plain"
            )
        
        metadata = doc.get("metadata", {})
        file_path = metadata.get("file_path")
        
        if not file_path:
            # No physical file - return content as text
            content = doc.get("content", "")
            if content:
                title = doc.get("title", "document")
                text_content = f"Title: {title}\n\n{content}"
                file_bytes = text_content.encode('utf-8')
                return Response(
                    content=file_bytes,
                    status_code=200,
                    media_type="text/plain; charset=utf-8"
                )
            return Response(
                content=b"No file or content",
                status_code=404,
                media_type="text/plain"
            )
        
        # Read file from local storage
        file_handler = FileHandler()
        file_content = await file_handler.get_file(file_path)
        
        if file_content is None:
            logger.warning(f"File not found locally: {file_path}")
            return Response(
                content=b"File not found on this node",
                status_code=404,
                media_type="text/plain"
            )
        
        content_type = metadata.get("content_type", "application/octet-stream")
        
        logger.info(f"Serving file for document {document_id} from {node_id}")
        
        return Response(
            content=file_content,
            status_code=200,
            media_type=content_type
        )
        
    except Exception as e:
        logger.error(f"Error fetching document file: {e}")
        return Response(
            content=f"Error: {str(e)}".encode(),
            status_code=500,
            media_type="text/plain"
        )


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


# =============================================================================
# Document Registry Synchronization Endpoints (Gossip Protocol)
# =============================================================================

class RegistrySyncRequest(BaseModel):
    """Request to sync registry entries from another node."""
    entries: list  # List of DocumentRegistryEntry dicts
    source_node: str


@router.post("/sync/registry")
async def sync_registry_entries(request: RegistrySyncRequest) -> Dict[str, Any]:
    """
    Receive registry entries from another node (gossip receive).
    
    This endpoint is called by other nodes to propagate document registry
    updates via the gossip protocol.
    """
    import os
    from .dependencies import get_document_registry
    from ..storage.user_document_registry import DocumentRegistryEntry
    
    try:
        doc_registry = await get_document_registry()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Convert dicts to DocumentRegistryEntry objects
        entries = [DocumentRegistryEntry.from_dict(e) for e in request.entries]
        
        # Merge with local registry
        merged = await doc_registry.merge_entries(entries)
        
        logger.info(f"Received {len(entries)} registry entries from {request.source_node}, merged {merged}")
        
        return {
            "status": "ok",
            "merged": merged,
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Error syncing registry: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/sync/registry/all")
async def get_all_registry_entries() -> Dict[str, Any]:
    """
    Get all registry entries from this node.
    
    Used for full sync during reconciliation after network partition.
    """
    import os
    from .dependencies import get_document_registry
    
    try:
        doc_registry = await get_document_registry()
        node_id = os.environ.get("NODE_ID", "unknown")
        
        # Get all entries (including tombstones for proper sync)
        entries = await doc_registry.get_all_entries(include_deleted=True)
        
        return {
            "status": "ok",
            "entries": [e.to_dict() for e in entries],
            "count": len(entries),
            "node_id": node_id
        }
        
    except Exception as e:
        logger.error(f"Error getting all registry entries: {e}")
        return {
            "status": "error",
            "message": str(e),
            "entries": [],
            "count": 0
        }


# =============================================================================
# Full Cluster Sync Endpoint (Post-Partition Reconciliation)
# =============================================================================

@router.post("/sync/full")
async def trigger_full_sync() -> Dict[str, Any]:
    """
    Trigger a full synchronization of all data.
    
    This should be called after a network partition heals to ensure
    all nodes have consistent data.
    """
    import os
    from .dependencies import get_document_registry, get_user_repository, get_cluster_manager, get_document_repository
    
    try:
        node_id = os.environ.get("NODE_ID", "unknown")
        results = {
            "node_id": node_id,
            "users_synced": 0,
            "registry_entries_synced": 0,
            "documents_verified": 0
        }
        
        # 1. Get cluster manager to find peers
        cluster_manager = await get_cluster_manager()
        nodes = cluster_manager.get_all_nodes()
        peers = [n for n in nodes if n.node_id != node_id]
        
        if not peers:
            return {"status": "ok", "message": "No peers to sync with", **results}
        
        # 2. Sync users from all peers
        user_repo = await get_user_repository()
        for peer in peers:
            try:
                import aiohttp
                address = peer.address
                port = getattr(peer, 'port', 8000) or 8000
                if ':' not in address:
                    address = f"{address}:{port}"
                
                url = f"http://{address}/api/v1/internal/sync/users"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for user_data in data.get("users", []):
                                try:
                                    existing = await user_repo.find_by_email(user_data.get("email", ""))
                                    if not existing:
                                        from ..storage.models import UserModel, UserStatus
                                        user = UserModel(
                                            id=user_data["id"],
                                            username=user_data["username"],
                                            email=user_data["email"],
                                            password_hash=user_data["password_hash"],
                                            salt=user_data["salt"],
                                            role=user_data.get("role", "user"),
                                            status=UserStatus.ACTIVE,
                                            full_name=user_data.get("full_name"),
                                        )
                                        await user_repo.create(user)
                                        results["users_synced"] += 1
                                except Exception as e:
                                    logger.debug(f"Could not sync user: {e}")
            except Exception as e:
                logger.warning(f"Failed to sync users from {peer.node_id}: {e}")
        
        # 3. Sync document registry
        doc_registry = await get_document_registry()
        for peer in peers:
            try:
                import aiohttp
                address = peer.address
                port = getattr(peer, 'port', 8000) or 8000
                if ':' not in address:
                    address = f"{address}:{port}"
                
                url = f"http://{address}/api/v1/internal/sync/registry/all"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            from ..storage.user_document_registry import DocumentRegistryEntry
                            entries = [DocumentRegistryEntry.from_dict(e) for e in data.get("entries", [])]
                            merged = await doc_registry.merge_entries(entries)
                            results["registry_entries_synced"] += merged
            except Exception as e:
                logger.warning(f"Failed to sync registry from {peer.node_id}: {e}")
        
        # 4. Sync missing documents AND apply tombstones
        results["documents_replicated"] = 0
        results["documents_deleted_by_tombstone"] = 0
        doc_repo = await get_document_repository()
        
        for peer in peers:
            try:
                import aiohttp
                import base64
                from ..storage.file_handler import FileHandler
                
                address = peer.address
                port = getattr(peer, 'port', 8000) or 8000
                if ':' not in address:
                    address = f"{address}:{port}"
                
                # Get document IDs from peer's registry (including deleted entries)
                registry_url = f"http://{address}/api/v1/internal/sync/registry/all"
                async with aiohttp.ClientSession() as session:
                    async with session.get(registry_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            continue
                        registry_data = await resp.json()
                        
                    # Check each document from peer's registry
                    for entry in registry_data.get("entries", []):
                        doc_id = entry.get("document_id")
                        if not doc_id:
                            continue
                        
                        # Handle tombstones: if document is deleted in registry, delete it locally
                        if entry.get("is_deleted", False):
                            local_doc = await doc_repo.find_by_id(doc_id)
                            if local_doc:
                                await doc_repo.delete(doc_id)
                                results["documents_deleted_by_tombstone"] += 1
                                logger.info(f"Deleted local document {doc_id} due to tombstone from {peer.node_id}")
                            continue  # Don't try to replicate a deleted document
                            
                        # Check if we have this document locally
                        local_doc = await doc_repo.find_by_id(doc_id)
                        if local_doc:
                            continue  # Already have it
                        
                        # Fetch the document from peer
                        doc_url = f"http://{address}/api/v1/internal/document/{doc_id}"
                        try:
                            async with session.get(doc_url, timeout=aiohttp.ClientTimeout(total=30)) as doc_resp:
                                if doc_resp.status != 200:
                                    continue
                                doc_data = await doc_resp.json()
                                
                                if doc_data.get("status") != "ok":
                                    continue
                                
                                document = doc_data.get("document", {})
                                if not document:
                                    continue
                                
                                # Check if document has a file and fetch it
                                file_content = None
                                metadata = document.get("metadata", {})
                                if metadata.get("file_path"):
                                    file_url = f"http://{address}/api/v1/internal/document/{doc_id}/file"
                                    try:
                                        async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=60)) as file_resp:
                                            if file_resp.status == 200:
                                                file_content = await file_resp.read()
                                    except Exception as e:
                                        logger.debug(f"Could not fetch file for {doc_id}: {e}")
                                
                                # Save document locally
                                document["_id"] = doc_id
                                document["is_replica"] = True
                                document["primary_node"] = entry.get("node_id", peer.node_id)
                                
                                # If we got file content, save it locally
                                if file_content:
                                    try:
                                        file_handler = FileHandler()
                                        filename = metadata.get("filename", f"{doc_id}.bin")
                                        content_type = metadata.get("content_type", "application/octet-stream")
                                        uploaded = await file_handler.save_file(
                                            file_data=file_content,
                                            filename=filename,
                                            content_type=content_type
                                        )
                                        if "metadata" not in document:
                                            document["metadata"] = {}
                                        document["metadata"]["file_path"] = uploaded.storage_path
                                        document["metadata"]["replica_file"] = True
                                    except Exception as e:
                                        logger.warning(f"Could not save file for {doc_id}: {e}")
                                
                                await doc_repo.create(document)
                                results["documents_replicated"] += 1
                                logger.info(f"Replicated missing document {doc_id} from {peer.node_id}")
                                
                        except Exception as e:
                            logger.debug(f"Could not fetch document {doc_id}: {e}")
                            
            except Exception as e:
                logger.warning(f"Failed to sync documents from {peer.node_id}: {e}")
        
        logger.info(f"Full sync completed: {results}")
        return {"status": "ok", **results}
        
    except Exception as e:
        logger.error(f"Full sync error: {e}")
        return {"status": "error", "message": str(e)}
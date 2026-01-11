"""
Documents API Router
CRUD endpoints for document management in DistriSearch
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import Response
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import logging
import uuid
import hashlib

from .schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentVectors,
    PaginationParams,
    ErrorResponse
)
from .dependencies import (
    get_document_repository,
    get_search_engine,
    get_cluster_manager,
    get_current_node,
    rate_limit_upload
)
from ..storage.mongodb import DocumentRepository
from ..storage.file_handler import FileHandler
from ..storage.content_extractor import ContentExtractor
from ..core.search import SearchEngine
from ..distributed.coordination import ClusterManager
from ..middleware.auth import require_auth, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# File handlers
file_handler = FileHandler()
content_extractor = ContentExtractor()


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document",
    responses={
        201: {"description": "Document created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        401: {"description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_document(
    document: DocumentCreate,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node),
    auth_user: dict = Depends(require_auth)
):
    """
    Create a new document in the distributed search system.
    
    The document will be:
    1. Vectorized using TF-IDF, MinHash, and LDA
    2. Assigned to a partition using VP-Tree
    3. Stored on the appropriate node
    4. Replicated according to the replication factor
    """
    try:
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow()
        owner_id = auth_user.get("user_id") or auth_user.get("id") or auth_user.get("sub")
        
        # Calculate content hash for deduplication
        content_hash = hashlib.sha256(
            f"{document.title}:{document.content}".encode()
        ).hexdigest()
        
        # Check for duplicate document (same owner, same content)
        existing = await doc_repo.find_one({
            "owner_id": owner_id,
            "content_hash": content_hash
        })
        if existing:
            # Return existing document instead of creating duplicate
            logger.info(f"Document already exists with same content hash: {existing.get('_id')}")
            return DocumentResponse(
                id=str(existing["_id"]),
                title=existing["title"],
                content=existing["content"],
                metadata=existing.get("metadata", {}),
                tags=existing.get("tags", []),
                node_id=existing.get("node_id"),
                partition_id=existing.get("partition_id"),
                vectors=DocumentVectors(**existing["vectors"]) if existing.get("vectors") else None,
                created_at=existing["created_at"],
                updated_at=existing["updated_at"]
            )
        
        # Generate vectors for the document
        vectors = await search_engine.vectorize_document(document.content)
        
        # Determine partition assignment using VP-Tree
        partition_id = await cluster_manager.assign_partition(vectors)
        node_id = await cluster_manager.get_node_for_partition(partition_id)
        
        # Create document model
        doc_data = {
            "_id": doc_id,
            "title": document.title,
            "content": document.content,
            "content_hash": content_hash,
            "metadata": document.metadata or {},
            "tags": document.tags or [],
            "owner_id": owner_id,
            "node_id": node_id,
            "partition_id": partition_id,
            "vectors": {
                "tfidf": vectors.get("tfidf", []),
                "minhash": vectors.get("minhash", []),
                "lda": vectors.get("lda", []),
                "textrank": vectors.get("textrank", [])
            },
            "created_at": now,
            "updated_at": now
        }
        
        # Store document
        await doc_repo.create(doc_data)
        
        # Replicate to other nodes (replication factor k=2)
        replication_result = await cluster_manager.replicate_document(
            doc_id=doc_id, 
            primary_node_id=node_id,
            document_data=doc_data
        )
        
        # Register document in user-document registry for eventual consistency queries
        try:
            from .dependencies import get_document_registry
            doc_registry = await get_document_registry()
            await doc_registry.register_document(
                user_id=doc_data["owner_id"],
                document_id=doc_id,
                node_id=node_id,
                title=document.title,
                filename=None,
            )
            logger.debug(f"Registered document {doc_id} in user-document registry")
        except Exception as e:
            logger.warning(f"Failed to register document in registry: {e}")
        
        logger.info(f"Document created: {doc_id} on node {node_id}, replicated_to: {replication_result.get('replicated_to', [])}")
        
        return DocumentResponse(
            id=doc_id,
            title=document.title,
            content=document.content,
            metadata=document.metadata or {},
            tags=document.tags or [],
            node_id=node_id,
            partition_id=partition_id,
            vectors=DocumentVectors(**doc_data["vectors"]),
            created_at=now,
            updated_at=now
        )
        
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document: {str(e)}"
        )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document file",
    dependencies=[Depends(rate_limit_upload)],
    responses={
        201: {"description": "File uploaded and processed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file"},
        401: {"description": "Authentication required"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node),
    auth_user: dict = Depends(require_auth)
):
    """
    Upload and process a document file.
    
    Supports ANY file type. For text-based files (PDF, DOCX, TXT, HTML, etc.),
    content will be extracted for full-text search. For binary files (images,
    audio, video, etc.), the file will be searchable by filename only.
    
    Maximum file size: 500MB
    
    The document will be:
    1. Content extracted from the file (if possible)
    2. Vectorized using TF-IDF, MinHash, and LDA (or filename-based for binary files)
    3. Assigned to a partition using VP-Tree
    4. Stored on the appropriate node
    """
    try:
        # Validate file
        max_size = 500 * 1024 * 1024  # 500MB
        content = await file.read()
        
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds maximum limit of 500MB"
            )
        
        # Save file and get metadata
        file_metadata = await file_handler.save_file(
            file_data=content,
            filename=file.filename,
            content_type=file.content_type
        )
        
        # Extract text content (may return empty for binary files)
        extraction_result = await content_extractor.extract(
            file_data=content,
            filename=file.filename,
            content_type=file.content_type
        )
        extracted_content = extraction_result.text
        
        # For files without extractable content, use filename for search
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow()
        doc_title = title or extraction_result.title or file.filename or "Untitled Document"
        doc_tags = tags.split(",") if tags else []
        owner_id = auth_user.get("user_id") or auth_user.get("id") or auth_user.get("sub")
        
        # Calculate content hash for deduplication (based on file content)
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicate file (same owner, same content)
        existing = await doc_repo.find_one({
            "owner_id": owner_id,
            "content_hash": content_hash
        })
        if existing:
            # Return existing document instead of creating duplicate
            logger.info(f"File already exists with same content hash: {existing.get('_id')}")
            content_preview = existing.get("content", "")[:500] if existing.get("content") else f"[Binary file: {file.filename}]"
            return DocumentUploadResponse(
                id=str(existing["_id"]),
                filename=existing.get("metadata", {}).get("filename", file.filename),
                title=existing["title"],
                content_preview=content_preview,
                file_size=existing.get("metadata", {}).get("file_size", len(content)),
                content_type=existing.get("metadata", {}).get("content_type", file.content_type),
                node_id=existing.get("node_id"),
                partition_id=existing.get("partition_id"),
                created_at=existing["created_at"]
            )
        
        # Determine searchable text: use extracted content or filename
        searchable_text = extracted_content.strip() if extracted_content else ""
        is_content_extracted = bool(searchable_text)
        
        if not searchable_text:
            # Use filename (without extension) as searchable text for binary files
            filename_without_ext = Path(file.filename).stem if file.filename else "unnamed"
            # Also include the extension as a searchable term
            file_ext = Path(file.filename).suffix.lower() if file.filename else ""
            searchable_text = f"{filename_without_ext} {file_ext.replace('.', '')}"
            logger.info(f"No content extracted from {file.filename}, using filename for search")
        
        # Generate vectors from searchable text
        vectors = await search_engine.vectorize_document(searchable_text)
        
        # Determine partition assignment
        partition_id = await cluster_manager.assign_partition(vectors)
        node_id = await cluster_manager.get_node_for_partition(partition_id)
        
        # Create document
        doc_data = {
            "_id": doc_id,
            "title": doc_title,
            "content": extracted_content if is_content_extracted else "",
            "content_hash": content_hash,
            "metadata": {
                "filename": file.filename,
                "content_type": file.content_type,
                "file_size": len(content),
                "file_path": file_metadata.storage_path,
                "content_extracted": is_content_extracted,
                "extraction_metadata": extraction_result.metadata,
            },
            "tags": doc_tags,
            "owner_id": owner_id,
            "node_id": node_id,
            "partition_id": partition_id,
            "vectors": {
                "tfidf": vectors.get("tfidf", []),
                "minhash": vectors.get("minhash", []),
                "lda": vectors.get("lda", []),
                "textrank": vectors.get("textrank", [])
            },
            "created_at": now,
            "updated_at": now
        }
        
        await doc_repo.create(doc_data)
        
        # Replicate to other nodes (replication factor k=2 means document exists on 2 nodes)
        # Always replicate from the node that stored it
        replication_result = await cluster_manager.replicate_document(
            doc_id=doc_id, 
            primary_node_id=node_id,
            document_data=doc_data
        )
        
        # Register document in user-document registry for eventual consistency queries
        try:
            from .dependencies import get_document_registry
            doc_registry = await get_document_registry()
            await doc_registry.register_document(
                user_id=doc_data["owner_id"],
                document_id=doc_id,
                node_id=node_id,
                title=doc_title,
                filename=file.filename,
            )
            logger.debug(f"Registered uploaded document {doc_id} in user-document registry")
        except Exception as e:
            logger.warning(f"Failed to register uploaded document in registry: {e}")
        
        logger.info(f"Document uploaded: {doc_id}, file: {file.filename}, content_extracted: {is_content_extracted}, replicated_to: {replication_result.get('replicated_to', [])}")
        
        content_preview = extracted_content[:500] if is_content_extracted else f"[Binary file: {file.filename}]"
        
        return DocumentUploadResponse(
            id=doc_id,
            filename=file.filename,
            title=doc_title,
            content_preview=content_preview,
            file_size=len(content),
            content_type=file.content_type,
            node_id=node_id,
            partition_id=partition_id,
            created_at=now
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    responses={
        200: {"description": "List of documents"},
        401: {"description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_documents(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    node_id: Optional[str] = Query(default=None, description="Filter by node"),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node),
    auth_user: dict = Depends(require_auth)
):
    """
    List documents uploaded by the current authenticated user.
    Federates query to all nodes to get complete view (documents are replicated with k=2).
    """
    import aiohttp
    import asyncio
    
    try:
        # Build filter - only show user's own documents
        user_id = auth_user.get("user_id") or auth_user.get("id") or auth_user.get("sub")
        filters = {"owner_id": user_id}
        if tag:
            filters["tags"] = tag
        if node_id:
            filters["node_id"] = node_id
        
        skip = (page - 1) * page_size
        
        # Collect documents from all nodes to get complete view
        all_documents = {}  # Use dict to deduplicate by document_id
        my_node_id = current_node.get("node_id", "unknown")
        
        # Get local documents first
        local_docs = await doc_repo.find(
            filters=filters,
            skip=0,
            limit=1000,  # Get all for deduplication
            sort=[("created_at", -1)]
        )
        for doc in local_docs:
            doc_id = str(doc["_id"])
            all_documents[doc_id] = doc
        
        # Federate to other nodes if we have cluster_manager
        if cluster_manager:
            try:
                nodes = await cluster_manager.get_cluster_nodes()
                other_nodes = [n for n in nodes if n.get("node_id") != my_node_id and n.get("status") == "healthy"]
                
                async def fetch_from_node(node_info):
                    try:
                        node_address = node_info.get("address", "")
                        port = node_info.get("port", 8000)
                        url = f"http://{node_address}:{port}/api/v1/internal/documents/list"
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                url,
                                json={"owner_id": user_id, "tag": tag},
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    return data.get("documents", [])
                    except Exception as e:
                        logger.warning(f"Failed to fetch documents from {node_info.get('node_id')}: {e}")
                    return []
                
                # Fetch from all other nodes in parallel
                if other_nodes:
                    tasks = [fetch_from_node(n) for n in other_nodes]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, list):
                            for doc in result:
                                doc_id = str(doc.get("_id") or doc.get("id", ""))
                                if doc_id and doc_id not in all_documents:
                                    all_documents[doc_id] = doc
            except Exception as e:
                logger.warning(f"Error federating document list: {e}")
        
        # Helper to safely get created_at as datetime for sorting
        def get_created_at(doc):
            created = doc.get("created_at")
            if created is None:
                return datetime.min
            if isinstance(created, datetime):
                return created
            if isinstance(created, str):
                try:
                    # Parse ISO format string
                    return datetime.fromisoformat(created.replace('Z', '+00:00'))
                except:
                    return datetime.min
            return datetime.min
        
        # Sort all documents by created_at descending
        sorted_docs = sorted(
            all_documents.values(),
            key=get_created_at,
            reverse=True
        )
        
        # Apply pagination
        total = len(sorted_docs)
        paginated_docs = sorted_docs[skip:skip + page_size]
        total_pages = (total + page_size - 1) // page_size
        
        # Convert to response models
        doc_responses = []
        for doc in paginated_docs:
            doc_responses.append(DocumentResponse(
                id=str(doc.get("_id") or doc.get("id", "")),
                title=doc.get("title", "Untitled"),
                content=doc.get("content", ""),
                metadata=doc.get("metadata", {}),
                tags=doc.get("tags", []),
                node_id=doc.get("node_id"),
                partition_id=doc.get("partition_id"),
                vectors=DocumentVectors(**doc["vectors"]) if doc.get("vectors") else None,
                created_at=doc.get("created_at", datetime.utcnow()),
                updated_at=doc.get("updated_at", datetime.utcnow())
            ))
        
        return DocumentListResponse(
            documents=doc_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document by ID",
    responses={
        200: {"description": "Document found"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_document(
    document_id: str,
    include_vectors: bool = Query(default=False, description="Include vectors in response"),
    doc_repo: DocumentRepository = Depends(get_document_repository)
):
    """
    Get a document by its ID.
    """
    try:
        doc = await doc_repo.find_by_id(document_id)
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        vectors = None
        if include_vectors and doc.get("vectors"):
            vectors = DocumentVectors(**doc["vectors"])
        
        return DocumentResponse(
            id=str(doc["_id"]),
            title=doc["title"],
            content=doc["content"],
            metadata=doc.get("metadata", {}),
            tags=doc.get("tags", []),
            node_id=doc.get("node_id"),
            partition_id=doc.get("partition_id"),
            vectors=vectors,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.get(
    "/{document_id}/download",
    summary="Download the document file",
    responses={
        200: {"description": "File content"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def download_document(
    document_id: str,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Download a document as a file.
    
    For uploaded files: Returns the original file.
    For text documents: Returns content as a .txt file.
    If file is not local: Fetches from other nodes in the cluster.
    """
    import aiohttp
    
    try:
        doc = await doc_repo.find_by_id(document_id)
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        metadata = doc.get("metadata", {})
        file_path = metadata.get("file_path")
        
        # Case 1: Document has a file path (uploaded file)
        if file_path:
            # Try to read locally first
            file_content = await file_handler.get_file(file_path)
            
            if file_content is not None:
                # File found locally
                original_filename = metadata.get("filename", "download")
                content_type = metadata.get("content_type", "application/octet-stream")
                
                return Response(
                    content=file_content,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{original_filename}"',
                        "Content-Length": str(len(file_content)),
                    }
                )
            
            # File not found locally - try to fetch from other nodes
            logger.info(f"File not found locally for {document_id}, trying other nodes...")
            
            if cluster_manager:
                primary_node = doc.get("node_id") or doc.get("primary_node")
                nodes = cluster_manager.get_healthy_nodes()
                
                for node in nodes:
                    if node.node_id == cluster_manager.node_id:
                        continue  # Skip self
                    
                    try:
                        port = getattr(node, 'port', 8000) or 8000
                        address = node.address
                        if ':' not in address:
                            address = f"{address}:{port}"
                        
                        url = f"http://{address}/api/v1/internal/document/{document_id}/file"
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                                if resp.status == 200:
                                    remote_content = await resp.read()
                                    original_filename = metadata.get("filename", "download")
                                    content_type = metadata.get("content_type", "application/octet-stream")
                                    
                                    logger.info(f"Fetched file for {document_id} from {node.node_id}")
                                    
                                    return Response(
                                        content=remote_content,
                                        media_type=content_type,
                                        headers={
                                            "Content-Disposition": f'attachment; filename="{original_filename}"',
                                            "Content-Length": str(len(remote_content)),
                                        }
                                    )
                    except Exception as e:
                        logger.debug(f"Could not fetch file from {node.node_id}: {e}")
                        continue
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on any node in the cluster"
            )
        
        # Case 2: Text document (no file_path) - generate .txt file from content
        content = doc.get("content", "")
        title = doc.get("title", "document")
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document has no content to download"
            )
        
        # Create text file content
        text_content = f"Title: {title}\n\n{content}"
        file_bytes = text_content.encode('utf-8')
        
        # Generate safe filename from title
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
        safe_title = safe_title.strip()[:50] or "document"
        filename = f"{safe_title}.txt"
        
        return Response(
            content=file_bytes,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download document: {str(e)}"
        )


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    responses={
        200: {"description": "Document updated successfully"},
        401: {"description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_document(
    document_id: str,
    update: DocumentUpdate,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    auth_user: dict = Depends(require_auth)
):
    """
    Update a document by its ID.
    
    If content is updated, the document will be re-vectorized and
    potentially moved to a different partition.
    """
    try:
        # Get existing document
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        update_data = {}
        
        if update.title is not None:
            update_data["title"] = update.title
        if update.metadata is not None:
            update_data["metadata"] = update.metadata
        if update.tags is not None:
            update_data["tags"] = update.tags
        
        # If content changed, re-vectorize
        if update.content is not None and update.content != doc["content"]:
            update_data["content"] = update.content
            vectors = await search_engine.vectorize_document(update.content)
            update_data["vectors"] = {
                "tfidf": vectors.get("tfidf", []),
                "minhash": vectors.get("minhash", []),
                "lda": vectors.get("lda", []),
                "textrank": vectors.get("textrank", [])
            }
            
            # Check if partition needs to change
            new_partition = await cluster_manager.assign_partition(vectors)
            if new_partition != doc.get("partition_id"):
                update_data["partition_id"] = new_partition
                new_node = await cluster_manager.get_node_for_partition(new_partition)
                update_data["node_id"] = new_node
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Update document
        await doc_repo.update(document_id, update_data)
        
        # Get updated document
        updated_doc = await doc_repo.find_by_id(document_id)
        
        logger.info(f"Document updated: {document_id}")
        
        return DocumentResponse(
            id=str(updated_doc["_id"]),
            title=updated_doc["title"],
            content=updated_doc["content"],
            metadata=updated_doc.get("metadata", {}),
            tags=updated_doc.get("tags", []),
            node_id=updated_doc.get("node_id"),
            partition_id=updated_doc.get("partition_id"),
            vectors=DocumentVectors(**updated_doc["vectors"]) if updated_doc.get("vectors") else None,
            created_at=updated_doc["created_at"],
            updated_at=updated_doc["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}"
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    responses={
        204: {"description": "Document deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Not authorized to delete this document"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_document(
    document_id: str,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    auth_user: dict = Depends(require_auth)
):
    """
    Delete a document by its ID.
    
    The document will be removed from all replicas.
    Only the document owner or an admin can delete a document.
    """
    try:
        # Check if document exists
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Check authorization: user must be owner or admin
        user_id = auth_user.get("user_id") or auth_user.get("id") or auth_user.get("sub")
        user_role = auth_user.get("role", "user")
        doc_owner = doc.get("owner_id")
        
        if user_role != "admin" and doc_owner and doc_owner != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this document. Only the owner can delete it."
            )
        
        # Delete from all replicas across the cluster (eventual consistency)
        deletion_result = await cluster_manager.delete_document_replicas(document_id)
        logger.info(f"Replica deletion result for {document_id}: {deletion_result}")
        
        # Delete from local database
        await doc_repo.delete(document_id)
        
        # Clean up file if exists
        if doc.get("metadata", {}).get("file_path"):
            try:
                await file_handler.delete_file(doc["metadata"]["file_path"])
            except Exception as e:
                logger.warning(f"Failed to delete file: {e}")
        
        # Mark document as deleted in user-document registry (tombstone)
        try:
            from .dependencies import get_document_registry
            doc_registry = await get_document_registry()
            await doc_registry.unregister_document(user_id=doc_owner, document_id=document_id)
            logger.info(f"Unregistered document {document_id} from registry for user {doc_owner}")
        except Exception as e:
            logger.warning(f"Failed to unregister document from registry: {e}")
        
        logger.info(f"Document deleted: {document_id} by user {user_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get(
    "/{document_id}/vectors",
    response_model=DocumentVectors,
    summary="Get document vectors",
    responses={
        200: {"description": "Document vectors"},
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def get_document_vectors(
    document_id: str,
    doc_repo: DocumentRepository = Depends(get_document_repository)
):
    """
    Get the vectorized representation of a document.
    """
    try:
        doc = await doc_repo.find_by_id(document_id)
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        vectors = doc.get("vectors", {})
        return DocumentVectors(
            tfidf=vectors.get("tfidf", []),
            minhash=vectors.get("minhash", []),
            lda=vectors.get("lda", []),
            textrank=vectors.get("textrank", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document vectors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document vectors: {str(e)}"
        )

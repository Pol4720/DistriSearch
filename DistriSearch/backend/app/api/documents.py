"""
Documents API Router
CRUD endpoints for document management in DistriSearch
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from typing import List, Optional
from datetime import datetime
import logging
import uuid

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# File handlers
file_handler = FileHandler()
content_extractor = ContentExtractor()


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document",
    responses={
        201: {"description": "Document created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_document(
    document: DocumentCreate,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager),
    current_node: dict = Depends(get_current_node)
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
            "metadata": document.metadata or {},
            "tags": document.tags or [],
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
        
        # If not on the target node, forward to correct node
        if node_id != current_node["node_id"]:
            await cluster_manager.replicate_document(doc_id, node_id)
        
        logger.info(f"Document created: {doc_id} on node {node_id}")
        
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
    current_node: dict = Depends(get_current_node)
):
    """
    Upload and process a document file.
    
    Supported formats: PDF, DOCX, TXT, HTML
    Maximum file size: 50MB
    
    The document will be:
    1. Content extracted from the file
    2. Vectorized using TF-IDF, MinHash, and LDA
    3. Assigned to a partition using VP-Tree
    4. Stored on the appropriate node
    """
    try:
        # Validate file
        max_size = 50 * 1024 * 1024  # 50MB
        content = await file.read()
        
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds maximum limit of 50MB"
            )
        
        # Save file and get metadata
        file_metadata = await file_handler.save_file(
            content=content,
            filename=file.filename,
            content_type=file.content_type
        )
        
        # Extract text content
        extracted_content = await content_extractor.extract_content(
            file_path=file_metadata.path,
            content_type=file.content_type
        )
        
        if not extracted_content or not extracted_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text content from file"
            )
        
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow()
        doc_title = title or file.filename or "Untitled Document"
        doc_tags = tags.split(",") if tags else []
        
        # Generate vectors
        vectors = await search_engine.vectorize_document(extracted_content)
        
        # Determine partition assignment
        partition_id = await cluster_manager.assign_partition(vectors)
        node_id = await cluster_manager.get_node_for_partition(partition_id)
        
        # Create document
        doc_data = {
            "_id": doc_id,
            "title": doc_title,
            "content": extracted_content,
            "metadata": {
                "filename": file.filename,
                "content_type": file.content_type,
                "file_size": len(content),
                "file_path": file_metadata.path
            },
            "tags": doc_tags,
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
        
        # Replicate if needed
        if node_id != current_node["node_id"]:
            await cluster_manager.replicate_document(doc_id, node_id)
        
        logger.info(f"Document uploaded: {doc_id}, file: {file.filename}")
        
        return DocumentUploadResponse(
            id=doc_id,
            filename=file.filename,
            title=doc_title,
            content_preview=extracted_content[:500],
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
    "/",
    response_model=DocumentListResponse,
    summary="List documents",
    responses={
        200: {"description": "List of documents"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_documents(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
    node_id: Optional[str] = Query(default=None, description="Filter by node"),
    doc_repo: DocumentRepository = Depends(get_document_repository)
):
    """
    List documents with pagination and optional filtering.
    """
    try:
        # Build filter
        filters = {}
        if tag:
            filters["tags"] = tag
        if node_id:
            filters["node_id"] = node_id
        
        skip = (page - 1) * page_size
        
        # Get documents and total count
        documents = await doc_repo.find(
            filters=filters,
            skip=skip,
            limit=page_size,
            sort=[("created_at", -1)]
        )
        total = await doc_repo.count(filters)
        total_pages = (total + page_size - 1) // page_size
        
        # Convert to response models
        doc_responses = []
        for doc in documents:
            doc_responses.append(DocumentResponse(
                id=str(doc["_id"]),
                title=doc["title"],
                content=doc["content"],
                metadata=doc.get("metadata", {}),
                tags=doc.get("tags", []),
                node_id=doc.get("node_id"),
                partition_id=doc.get("partition_id"),
                vectors=DocumentVectors(**doc["vectors"]) if doc.get("vectors") else None,
                created_at=doc["created_at"],
                updated_at=doc["updated_at"]
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


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    responses={
        200: {"description": "Document updated successfully"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_document(
    document_id: str,
    update: DocumentUpdate,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    search_engine: SearchEngine = Depends(get_search_engine),
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
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
        404: {"model": ErrorResponse, "description": "Document not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_document(
    document_id: str,
    doc_repo: DocumentRepository = Depends(get_document_repository),
    cluster_manager: ClusterManager = Depends(get_cluster_manager)
):
    """
    Delete a document by its ID.
    
    The document will be removed from all replicas.
    """
    try:
        # Check if document exists
        doc = await doc_repo.find_by_id(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Delete from all replicas
        await cluster_manager.delete_document_replicas(document_id)
        
        # Delete from database
        await doc_repo.delete(document_id)
        
        # Clean up file if exists
        if doc.get("metadata", {}).get("file_path"):
            try:
                await file_handler.delete_file(doc["metadata"]["file_path"])
            except Exception as e:
                logger.warning(f"Failed to delete file: {e}")
        
        logger.info(f"Document deleted: {document_id}")
        
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

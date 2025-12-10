"""
File Handler for DistriSearch.

Handles file uploads, storage, and management.
"""

import asyncio
import hashlib
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
import uuid
import aiofiles
import aiofiles.os

logger = logging.getLogger(__name__)


@dataclass
class UploadedFile:
    """
    Represents an uploaded file.
    
    Attributes:
        id: Unique file identifier
        filename: Original filename
        content_type: MIME type
        size: File size in bytes
        hash: File content hash (SHA-256)
        storage_path: Path where file is stored
        uploaded_at: Upload timestamp
        metadata: Additional file metadata
    """
    id: str
    filename: str
    content_type: str
    size: int
    hash: str
    storage_path: str
    uploaded_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "hash": self.hash,
            "storage_path": self.storage_path,
            "uploaded_at": self.uploaded_at.isoformat(),
            "metadata": self.metadata,
        }


class FileHandler:
    """
    Handler for file uploads and storage.
    
    Features:
    - Async file operations
    - Content hashing
    - File type validation
    - Storage management
    """
    
    # Supported file types
    SUPPORTED_TYPES = {
        # Documents
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        # Text
        "text/plain": ".txt",
        "text/html": ".html",
        "text/markdown": ".md",
        "text/csv": ".csv",
        "application/json": ".json",
        "application/xml": ".xml",
        "text/xml": ".xml",
        # Other
        "application/rtf": ".rtf",
        "application/epub+zip": ".epub",
    }
    
    # Maximum file size (50 MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    def __init__(
        self,
        storage_path: str = "/data/uploads",
        max_file_size: int = None,
    ):
        """
        Initialize file handler.
        
        Args:
            storage_path: Base path for file storage
            max_file_size: Maximum file size in bytes
        """
        self.storage_path = Path(storage_path)
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE
        
        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FileHandler initialized at {storage_path}")
    
    async def save_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UploadedFile:
        """
        Save an uploaded file.
        
        Args:
            file_data: File content bytes
            filename: Original filename
            content_type: MIME type
            metadata: Additional metadata
            
        Returns:
            UploadedFile object
            
        Raises:
            ValueError: If file type not supported or too large
        """
        # Validate file type
        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {content_type}")
        
        # Validate file size
        if len(file_data) > self.max_file_size:
            raise ValueError(
                f"File too large: {len(file_data)} bytes "
                f"(max: {self.max_file_size})"
            )
        
        # Generate file ID and hash
        file_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        # Determine storage path
        # Use hash-based directory structure for efficient lookup
        dir_path = self.storage_path / file_hash[:2] / file_hash[2:4]
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Use safe filename
        safe_filename = self._sanitize_filename(filename)
        extension = self.SUPPORTED_TYPES.get(content_type, "")
        storage_filename = f"{file_id}{extension}"
        file_path = dir_path / storage_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        logger.info(f"Saved file {filename} as {file_path}")
        
        return UploadedFile(
            id=file_id,
            filename=safe_filename,
            content_type=content_type,
            size=len(file_data),
            hash=file_hash,
            storage_path=str(file_path),
            metadata=metadata or {},
        )
    
    async def save_stream(
        self,
        stream: BinaryIO,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UploadedFile:
        """
        Save a file from a stream.
        
        Args:
            stream: File-like object
            filename: Original filename
            content_type: MIME type
            metadata: Additional metadata
            
        Returns:
            UploadedFile object
        """
        # Validate file type
        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {content_type}")
        
        # Generate file ID
        file_id = str(uuid.uuid4())
        
        # Create temp path
        temp_dir = self.storage_path / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        extension = self.SUPPORTED_TYPES.get(content_type, "")
        temp_path = temp_dir / f"{file_id}{extension}"
        
        # Save stream to temp file and calculate hash
        hasher = hashlib.sha256()
        total_size = 0
        
        async with aiofiles.open(temp_path, 'wb') as f:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                
                total_size += len(chunk)
                if total_size > self.max_file_size:
                    await aiofiles.os.remove(temp_path)
                    raise ValueError(f"File too large (max: {self.max_file_size})")
                
                hasher.update(chunk)
                await f.write(chunk)
        
        file_hash = hasher.hexdigest()
        
        # Move to final location
        dir_path = self.storage_path / file_hash[:2] / file_hash[2:4]
        dir_path.mkdir(parents=True, exist_ok=True)
        
        safe_filename = self._sanitize_filename(filename)
        storage_filename = f"{file_id}{extension}"
        file_path = dir_path / storage_filename
        
        shutil.move(str(temp_path), str(file_path))
        
        logger.info(f"Saved stream {filename} as {file_path}")
        
        return UploadedFile(
            id=file_id,
            filename=safe_filename,
            content_type=content_type,
            size=total_size,
            hash=file_hash,
            storage_path=str(file_path),
            metadata=metadata or {},
        )
    
    async def get_file(self, file_path: str) -> Optional[bytes]:
        """
        Read a file from storage.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content bytes or None
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except FileNotFoundError:
            return None
    
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if deleted
        """
        try:
            await aiofiles.os.remove(file_path)
            logger.info(f"Deleted file {file_path}")
            return True
        except FileNotFoundError:
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(file_path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove path separators
        filename = os.path.basename(filename)
        
        # Replace unsafe characters
        unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255 - len(ext)] + ext
        
        return filename
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(self.storage_path):
            for file in files:
                if file != ".gitkeep":
                    total_files += 1
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "storage_path": str(self.storage_path),
        }
    
    async def cleanup_temp(self):
        """Clean up temporary files."""
        temp_dir = self.storage_path / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cleaned up temp files")

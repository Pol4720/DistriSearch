from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import enum

class FileType(str, enum.Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"

class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class FileMeta(BaseModel):
    file_id: str  # SHA256 hash del archivo
    name: str
    path: str
    size: int  # En bytes
    mime_type: str
    type: FileType
    node_id: str
    last_updated: datetime = Field(default_factory=datetime.now)

class NodeInfo(BaseModel):
    node_id: str
    name: str
    ip_address: str
    port: int
    status: NodeStatus = NodeStatus.UNKNOWN
    last_seen: datetime = Field(default_factory=datetime.now)
    shared_files_count: int = 0

class SearchQuery(BaseModel):
    query: str
    file_type: Optional[FileType] = None
    max_results: int = 50

class SearchResult(BaseModel):
    files: List[FileMeta]
    total_count: int
    nodes_available: List[NodeInfo]

class DownloadRequest(BaseModel):
    file_id: str
    preferred_node_id: Optional[str] = None

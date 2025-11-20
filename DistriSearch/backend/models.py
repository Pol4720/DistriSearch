from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    activities = relationship("Activity", back_populates="user")

class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)  # e.g., "upload", "search", "download"
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="activities")

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
    # Identificador único de instancia del fichero (estable por nodo+path)
    file_id: str
    name: str
    path: str
    size: int  # En bytes
    mime_type: str
    type: FileType
    node_id: str
    last_updated: datetime = Field(default_factory=datetime.now)
    # Contenido textual (opcional, truncado para indexación full-text). No se persiste en la tabla principal.
    content: Optional[str] = None
    # Hash del contenido (opcional). Puede omitirse en ficheros muy grandes para evitar coste.
    content_hash: Optional[str] = None

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

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class DownloadRequest(BaseModel):
    file_id: str
    preferred_node_id: Optional[str] = None

class NodeRegistration(BaseModel):
    """Modelo simplificado para registro dinámico de nodos"""
    node_id: str
    name: Optional[str] = None
    ip_address: Optional[str] = None  # Opcional: si no se proporciona, usamos la IP de la solicitud
    port: int = 8080  # Puerto por defecto para agentes
    shared_folder: Optional[str] = None  # Ruta de la carpeta compartida (si es local)
    auto_scan: bool = False  # Si debe escanear automáticamente al registrarse
    
    class Config:
        schema_extra = {
            "example": {
                "node_id": "agent_dynamic_01",
                "name": "Agente Dynamico 1",
                "port": 8081,
                "shared_folder": "/app/shared",
                "auto_scan": True
            }
        }
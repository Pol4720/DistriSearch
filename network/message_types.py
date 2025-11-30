"""
Tipos de mensajes para comunicación entre nodos.
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import time


class MessageType(Enum):
    """Tipos de mensajes en el sistema distribuido."""
    
    # Mensajes de búsqueda
    SEARCH = "search"
    SEARCH_RESPONSE = "search_response"
    
    # Mensajes de documentos
    ADD_DOCUMENT = "add_document"
    ADD_DOCUMENT_RESPONSE = "add_document_response"
    REPLICATE_DOCUMENT = "replicate_document"
    
    # Mensajes de routing
    ROUTE_MESSAGE = "route_message"
    
    # Mensajes de Raft
    RAFT_MESSAGE = "raft_message"
    REQUEST_VOTE = "request_vote"
    VOTE_RESPONSE = "vote_response"
    APPEND_ENTRIES = "append_entries"
    APPEND_RESPONSE = "append_response"
    
    # Mensajes de Data Balancer
    UPDATE_INDEX = "update_index"
    LOCATE_TERMS = "locate_terms"
    LOCATE_RESPONSE = "locate_response"
    
    # Mensajes de control
    HEARTBEAT = "heartbeat"
    PING = "ping"
    PONG = "pong"
    
    # Mensajes de sharding
    SHARD_QUERY = "shard_query"
    SHARD_RESPONSE = "shard_response"


@dataclass
class Message:
    """Mensaje genérico entre nodos."""
    
    type: str  # MessageType
    sender_id: int
    receiver_id: int
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            "type": self.type,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_id": self.message_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        """Crea desde diccionario."""
        return cls(
            type=data["type"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
            message_id=data.get("message_id")
        )
    
    def is_type(self, message_type: MessageType) -> bool:
        """Verifica si es de un tipo específico."""
        return self.type == message_type.value

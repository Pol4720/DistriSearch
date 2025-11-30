"""
Modelo de documento para el índice invertido.
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict
import json


@dataclass
class Document:
    """Representa un documento indexado."""
    doc_id: str
    content: str
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serializa a JSON."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Document':
        """Deserializa desde diccionario."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Document':
        """Deserializa desde JSON."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class PostingEntry:
    """Entrada en posting list (doc_id + score)."""
    doc_id: str
    score: float
    
    def to_dict(self) -> Dict:
        return {"doc_id": self.doc_id, "score": self.score}


class DocumentStore:
    """Almacén de documentos en memoria."""
    
    def __init__(self):
        self.documents: Dict[str, Document] = {}
    
    def add(self, document: Document) -> None:
        """Añade un documento al almacén."""
        self.documents[document.doc_id] = document
    
    def get(self, doc_id: str) -> Optional[Document]:
        """Obtiene un documento por ID."""
        return self.documents.get(doc_id)
    
    def remove(self, doc_id: str) -> bool:
        """Elimina un documento."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False
    
    def exists(self, doc_id: str) -> bool:
        """Verifica si un documento existe."""
        return doc_id in self.documents
    
    def get_all(self) -> list[Document]:
        """Retorna todos los documentos."""
        return list(self.documents.values())
    
    def count(self) -> int:
        """Retorna número de documentos."""
        return len(self.documents)
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            doc_id: doc.to_dict()
            for doc_id, doc in self.documents.items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DocumentStore':
        """Deserializa desde diccionario."""
        store = cls()
        for doc_id, doc_data in data.items():
            store.documents[doc_id] = Document.from_dict(doc_data)
        return store

"""
Módulo de almacenamiento - Wrapper de compatibilidad.
DEPRECADO: Usar storage/inverted_index.py en su lugar.
"""
import logging
from pathlib import Path
from storage.inverted_index import InvertedIndex
from storage.persistence import IndexPersistence
from storage.document import Document, PostingEntry
from storage.tokenizer import Tokenizer

logger = logging.getLogger(__name__)

# Re-exportar para compatibilidad
__all__ = ['InvertedIndex', 'Document', 'PostingEntry', 'Tokenizer', 'LocalStorage']


class LocalStorage:
    """
    Wrapper de compatibilidad para código antiguo.
    
    DEPRECADO: Usar InvertedIndex + IndexPersistence directamente.
    """
    
    def __init__(self, data_dir: str = "data"):
        logger.warning(
            "LocalStorage está deprecado. "
            "Usa 'from storage.inverted_index import InvertedIndex'"
        )
        
        self.data_dir = Path(data_dir)
        self.index_file = self.data_dir / "index.json"
        self.index = IndexPersistence.load(self.index_file)
        self.tokenizer = Tokenizer()
    
    def add_document(self, doc_id: str, content: str, metadata: dict = None):
        return self.index.add_document(doc_id, content, metadata)
    
    def remove_document(self, doc_id: str):
        return self.index.remove_document(doc_id)
    
    def search(self, query: str, top_k: int = 10):
        return self.index.search(query, top_k)
    
    def get_document(self, doc_id: str):
        return self.index.get_document(doc_id)
    
    def tokenize(self, text: str):
        return self.tokenizer.tokenize(text)
    
    def save(self):
        IndexPersistence.save(self.index, self.index_file)
    
    def load(self):
        self.index = IndexPersistence.load(self.index_file)

"""
Módulo de almacenamiento distribuido.
Gestiona documentos, índices invertidos y persistencia.
"""
from storage.document import Document, DocumentStore
from storage.inverted_index import InvertedIndex
from storage.tokenizer import tokenize, remove_stopwords
from storage.persistence import PersistenceManager

__all__ = [
    "Document",
    "DocumentStore",
    "InvertedIndex",
    "tokenize",
    "remove_stopwords",
    "PersistenceManager",
]

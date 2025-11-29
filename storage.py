"""
Indexador local: índice invertido y persistencia.
"""
import json
import logging
import os
import re
import shelve
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Representa un documento indexado."""
    doc_id: str
    content: str
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PostingEntry:
    """Entrada en la lista de postings (índice invertido)."""
    doc_id: str
    score: float = 1.0  # Simple: term frequency


class InvertedIndex:
    """
    Índice invertido local para búsqueda de documentos.
    
    Estructura: término -> lista de (doc_id, score)
    """
    
    # Stopwords simples en español
    STOPWORDS = {
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
        'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
        'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for',
        'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by'
    }
    
    def __init__(self, node_id: int, persist_path: str = None):
        """
        Inicializa el índice invertido.
        
        Args:
            node_id: ID del nodo (para nombres de archivo)
            persist_path: Directorio para persistencia
        """
        self.node_id = node_id
        self.persist_path = persist_path or f"data/node_{node_id}"
        
        # Índice: término -> {doc_id: score}
        self.index: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Documentos: doc_id -> Document
        self.documents: Dict[str, Document] = {}
        
        # Asegurar que existe el directorio
        os.makedirs(self.persist_path, exist_ok=True)
        
        self.load()
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokeniza texto en términos.
        
        Args:
            text: Texto a tokenizar
        
        Returns:
            Lista de tokens (lowercase, sin stopwords)
        """
        # Lowercase y split por no-alfanuméricos
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        
        # Filtrar stopwords y tokens muy cortos
        tokens = [t for t in tokens if t not in self.STOPWORDS and len(t) > 2]
        
        return tokens
    
    def add_document(self, doc_id: str, content: str, metadata: Dict = None) -> Set[str]:
        """
        Añade un documento al índice.
        
        Args:
            doc_id: ID único del documento
            content: Contenido del documento
            metadata: Metadatos opcionales
        
        Returns:
            Set de términos únicos extraídos
        """
        doc = Document(doc_id=doc_id, content=content, metadata=metadata or {})
        self.documents[doc_id] = doc
        
        # Tokenizar
        tokens = self.tokenize(content)
        
        # Calcular term frequency
        term_freq = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
        
        # Actualizar índice invertido
        terms_added = set()
        for term, freq in term_freq.items():
            self.index[term][doc_id] = float(freq)
            terms_added.add(term)
        
        logger.info(f"Indexado doc {doc_id}: {len(terms_added)} términos únicos")
        
        return terms_added
    
    def remove_document(self, doc_id: str) -> Set[str]:
        """
        Elimina un documento del índice.
        
        Args:
            doc_id: ID del documento a eliminar
        
        Returns:
            Set de términos que ya no están en el índice
        """
        if doc_id not in self.documents:
            return set()
        
        del self.documents[doc_id]
        
        # Eliminar de índice invertido
        terms_removed = set()
        terms_to_delete = []
        
        for term, postings in self.index.items():
            if doc_id in postings:
                del postings[doc_id]
                if not postings:  # Ya no hay docs con este término
                    terms_to_delete.append(term)
                    terms_removed.add(term)
        
        for term in terms_to_delete:
            del self.index[term]
        
        logger.info(f"Eliminado doc {doc_id}: {len(terms_removed)} términos removidos")
        
        return terms_removed
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Busca documentos relevantes para la consulta.
        
        Args:
            query: Consulta de búsqueda
            top_k: Número de resultados a retornar
        
        Returns:
            Lista de (doc_id, score) ordenados por relevancia
        """
        query_terms = self.tokenize(query)
        
        if not query_terms:
            return []
        
        # Acumular scores por documento
        doc_scores = defaultdict(float)
        
        for term in query_terms:
            if term in self.index:
                for doc_id, score in self.index[term].items():
                    doc_scores[doc_id] += score
        
        # Ordenar por score descendente
        results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def get_terms(self) -> Set[str]:
        """Retorna todos los términos en el índice."""
        return set(self.index.keys())
    
    def get_document(self, doc_id: str) -> Document:
        """Obtiene un documento por su ID."""
        return self.documents.get(doc_id)
    
    def save(self):
        """Persiste el índice y documentos a disco."""
        index_file = os.path.join(self.persist_path, "index.json")
        docs_file = os.path.join(self.persist_path, "documents.json")
        
        try:
            # Guardar índice
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.index), f, ensure_ascii=False, indent=2)
            
            # Guardar documentos
            docs_dict = {doc_id: asdict(doc) for doc_id, doc in self.documents.items()}
            with open(docs_file, 'w', encoding='utf-8') as f:
                json.dump(docs_dict, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Índice guardado en {self.persist_path}")
        except Exception as e:
            logger.error(f"Error guardando índice: {e}")
    
    def load(self):
        """Carga el índice y documentos desde disco."""
        index_file = os.path.join(self.persist_path, "index.json")
        docs_file = os.path.join(self.persist_path, "documents.json")
        
        try:
            # Cargar índice
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.index = defaultdict(dict, loaded)
            
            # Cargar documentos
            if os.path.exists(docs_file):
                with open(docs_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.documents = {
                        doc_id: Document(**doc_data) 
                        for doc_id, doc_data in loaded.items()
                    }
            
            logger.info(f"Índice cargado: {len(self.index)} términos, {len(self.documents)} docs")
        except Exception as e:
            logger.warning(f"Error cargando índice: {e}")
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del índice."""
        return {
            'num_terms': len(self.index),
            'num_documents': len(self.documents),
            'total_postings': sum(len(postings) for postings in self.index.values())
        }

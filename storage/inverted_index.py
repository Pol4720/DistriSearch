"""
Índice invertido para búsqueda de documentos.
Estructura: término -> lista de (doc_id, score)
"""
import logging
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from storage.document import Document, PostingEntry
from storage.tokenizer import Tokenizer

logger = logging.getLogger(__name__)


class InvertedIndex:
    """
    Índice invertido local para búsqueda eficiente.
    
    Responsabilidades:
    - Indexar documentos (añadir/eliminar)
    - Buscar por términos
    - Calcular relevancia (TF-IDF simplificado)
    """
    
    def __init__(self, node_id: int = None, persist_path: str = None):
        # ID del nodo (opcional, para compatibilidad)
        self.node_id = node_id
        
        # Path de persistencia (opcional)
        self.persist_path = persist_path
        
        # Índice: término -> lista de PostingEntry
        self.index: Dict[str, List[PostingEntry]] = defaultdict(list)
        
        # Almacén de documentos: doc_id -> Document
        self.documents: Dict[str, Document] = {}
        
        # Tokenizador
        self.tokenizer = Tokenizer()
        
        # Estadísticas
        self.num_terms = 0
        self.num_documents = 0
    
    def add_document(self, doc_id: str, content: str, metadata: Dict = None) -> Set[str]:
        """
        Indexa un documento.
        
        Args:
            doc_id: ID único del documento
            content: Contenido textual
            metadata: Metadata opcional
            
        Returns:
            Conjunto de términos indexados
        """
        # Crear documento
        doc = Document(doc_id, content, metadata)
        
        # Si ya existía, eliminarlo primero
        if doc_id in self.documents:
            self.remove_document(doc_id)
        
        # Tokenizar
        tokens = self.tokenizer.tokenize(content)
        
        # Calcular frecuencia de términos (TF)
        term_freq = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
        
        # Indexar cada término
        terms_added = set()
        for term, freq in term_freq.items():
            # Score simple: frecuencia normalizada
            score = freq / len(tokens) if tokens else 0.0
            
            posting = PostingEntry(doc_id, score)
            self.index[term].append(posting)
            terms_added.add(term)
        
        # Guardar documento
        self.documents[doc_id] = doc
        
        # Actualizar estadísticas
        self.num_documents = len(self.documents)
        self.num_terms = len(self.index)
        
        logger.debug(
            f"Documento {doc_id} indexado: {len(terms_added)} términos únicos"
        )
        
        return terms_added
    
    def remove_document(self, doc_id: str) -> Set[str]:
        """
        Elimina un documento del índice.
        
        Args:
            doc_id: ID del documento a eliminar
            
        Returns:
            Conjunto de términos afectados
        """
        if doc_id not in self.documents:
            return set()
        
        # Eliminar de posting lists
        terms_removed = set()
        for term, postings in list(self.index.items()):
            self.index[term] = [p for p in postings if p.doc_id != doc_id]
            
            # Si la posting list quedó vacía, eliminar el término
            if not self.index[term]:
                del self.index[term]
                terms_removed.add(term)
        
        # Eliminar documento
        del self.documents[doc_id]
        
        # Actualizar estadísticas
        self.num_documents = len(self.documents)
        self.num_terms = len(self.index)
        
        logger.debug(f"Documento {doc_id} eliminado: {len(terms_removed)} términos afectados")
        
        return terms_removed
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Busca documentos relevantes para una query.
        
        Args:
            query: Texto de búsqueda
            top_k: Número máximo de resultados
            
        Returns:
            Lista de (doc_id, score) ordenada por relevancia
        """
        # Tokenizar query
        query_terms = self.tokenizer.tokenize(query)
        
        if not query_terms:
            return []
        
        # Acumular scores por documento
        doc_scores: Dict[str, float] = defaultdict(float)
        
        for term in query_terms:
            if term in self.index:
                for posting in self.index[term]:
                    doc_scores[posting.doc_id] += posting.score
        
        # Ordenar por score descendente
        sorted_results = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_results[:top_k]
    
    def get_document(self, doc_id: str) -> Document:
        """Obtiene un documento por ID."""
        return self.documents.get(doc_id)
    
    def get_term_nodes(self, term: str) -> bool:
        """Verifica si un término está en el índice local."""
        return term in self.index
    
    def tokenize(self, text: str) -> List[str]:
        """Wrapper de compatibilidad para tokenización."""
        return self.tokenizer.tokenize(text)
    
    def get_terms(self) -> Set[str]:
        """Retorna todos los términos indexados."""
        return set(self.index.keys())
    
    def save(self, filepath: str = None) -> None:
        """Wrapper de compatibilidad para save (no hace nada, usa persistence)."""
        pass
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            "index": {
                term: [p.to_dict() for p in postings]
                for term, postings in self.index.items()
            },
            "documents": {
                doc_id: doc.to_dict()
                for doc_id, doc in self.documents.items()
            },
            "num_terms": self.num_terms,
            "num_documents": self.num_documents
        }
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del índice."""
        return {
            "num_terms": self.num_terms,
            "num_documents": self.num_documents,
            "avg_postings_per_term": (
                sum(len(postings) for postings in self.index.values()) / self.num_terms
                if self.num_terms > 0 else 0
            )
        }

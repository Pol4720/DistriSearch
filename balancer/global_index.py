"""
Índice global de términos a nodos.
"""
from typing import Dict, Set, List
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class GlobalIndex:
    """Índice global: término -> conjunto de nodos que lo contienen."""
    
    def __init__(self):
        # término -> set de node_ids
        self.index: Dict[str, Set[int]] = defaultdict(set)
        
        # node_id -> set de términos
        self.node_terms: Dict[int, Set[str]] = defaultdict(set)
    
    def add_term(self, term: str, node_id: int):
        """
        Registra que un nodo contiene un término.
        
        Args:
            term: Término
            node_id: ID del nodo
        """
        self.index[term].add(node_id)
        self.node_terms[node_id].add(term)
        
        logger.debug(f"GlobalIndex: Término '{term}' añadido a nodo {node_id}")
    
    def remove_term(self, term: str, node_id: int):
        """
        Remueve la asociación término-nodo.
        
        Args:
            term: Término
            node_id: ID del nodo
        """
        if term in self.index:
            self.index[term].discard(node_id)
            
            # Si no quedan nodos, eliminar término
            if not self.index[term]:
                del self.index[term]
        
        if node_id in self.node_terms:
            self.node_terms[node_id].discard(term)
    
    def get_nodes_for_term(self, term: str) -> Set[int]:
        """
        Retorna los nodos que contienen un término.
        
        Args:
            term: Término a buscar
            
        Returns:
            Conjunto de node_ids
        """
        return self.index.get(term, set()).copy()
    
    def get_nodes_for_terms(self, terms: List[str]) -> Set[int]:
        """
        Retorna los nodos que contienen ALGUNO de los términos.
        
        Args:
            terms: Lista de términos
            
        Returns:
            Conjunto de node_ids
        """
        result = set()
        
        for term in terms:
            result |= self.get_nodes_for_term(term)
        
        return result
    
    def remove_node(self, node_id: int):
        """
        Remueve todas las entradas de un nodo.
        
        Args:
            node_id: ID del nodo a remover
        """
        if node_id not in self.node_terms:
            return
        
        # Copiar términos (para evitar modificar durante iteración)
        terms = list(self.node_terms[node_id])
        
        for term in terms:
            self.remove_term(term, node_id)
        
        # Limpiar
        if node_id in self.node_terms:
            del self.node_terms[node_id]
        
        logger.info(f"GlobalIndex: Nodo {node_id} removido completamente")
    
    def get_term_count(self) -> int:
        """Retorna el número total de términos únicos."""
        return len(self.index)
    
    def get_node_count(self) -> int:
        """Retorna el número de nodos registrados."""
        return len(self.node_terms)
    
    def contains_term(self, term: str) -> bool:
        """Verifica si un término existe en el índice."""
        return term in self.index
    
    def get_all_terms(self) -> List[str]:
        """Retorna todos los términos en el índice."""
        return list(self.index.keys())
    
    def get_terms_for_node(self, node_id: int) -> Set[str]:
        """Retorna todos los términos de un nodo."""
        return self.node_terms.get(node_id, set()).copy()
    
    def clear(self):
        """Limpia el índice completo."""
        self.index.clear()
        self.node_terms.clear()
        logger.info("GlobalIndex: Índice limpiado")
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            "index": {
                term: list(node_ids)
                for term, node_ids in self.index.items()
            }
        }
    
    def from_dict(self, data: Dict):
        """Carga desde diccionario."""
        self.clear()
        
        index_data = data.get("index", {})
        
        for term, node_ids in index_data.items():
            for node_id in node_ids:
                self.add_term(term, node_id)
        
        logger.info(
            f"GlobalIndex: Cargado ({self.get_term_count()} términos, "
            f"{self.get_node_count()} nodos)"
        )

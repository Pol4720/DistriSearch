"""
Data Balancer principal.
Gestiona el índice global y la localización de términos.
"""
from typing import List, Set, Dict, Optional
import logging
from balancer.global_index import GlobalIndex
from balancer.node_registry import NodeRegistry

logger = logging.getLogger(__name__)


class DataBalancer:
    """
    Data Balancer distribuido.
    Gestiona el índice global y localización de términos.
    """
    
    def __init__(self, node_id: int = None):
        """
        Inicializa el Data Balancer.
        
        Args:
            node_id: ID del nodo balancer (opcional)
        """
        self.node_id = node_id
        
        self.global_index = GlobalIndex()
        self.node_registry = NodeRegistry()
        
        logger.info(f"DataBalancer {node_id}: Inicializado")
    
    def register_node(
        self, 
        node_id: int, 
        address: str = None, 
        port: int = None
    ):
        """
        Registra un nodo en el sistema.
        
        Args:
            node_id: ID del nodo
            address: Dirección IP/hostname
            port: Puerto
        """
        self.node_registry.register(node_id, address, port)
        logger.info(f"DataBalancer: Nodo {node_id} registrado")
    
    def unregister_node(self, node_id: int):
        """
        Desregistra un nodo del sistema.
        
        Args:
            node_id: ID del nodo
        """
        # Remover del índice global
        self.global_index.remove_node(node_id)
        
        # Remover del registro
        self.node_registry.unregister(node_id)
        
        logger.info(f"DataBalancer: Nodo {node_id} desregistrado")
    
    def update_node_index(self, node_id: int, terms: List[str]):
        """
        Actualiza el índice global con los términos de un nodo.
        
        Args:
            node_id: ID del nodo
            terms: Lista de términos únicos en el nodo
        """
        # Remover términos viejos
        old_terms = self.global_index.get_terms_for_node(node_id)
        for term in old_terms:
            if term not in terms:
                self.global_index.remove_term(term, node_id)
        
        # Añadir términos nuevos
        for term in terms:
            self.global_index.add_term(term, node_id)
        
        # Actualizar stats
        self.node_registry.update_stats(
            node_id,
            doc_count=0,  # Se actualiza con heartbeat
            term_count=len(terms)
        )
        
        logger.debug(
            f"DataBalancer: Índice de nodo {node_id} actualizado "
            f"({len(terms)} términos)"
        )
    
    def locate_terms(self, terms: List[str]) -> Set[int]:
        """
        Localiza qué nodos contienen los términos dados.
        
        Args:
            terms: Lista de términos a buscar
            
        Returns:
            Conjunto de node_ids que contienen algún término
        """
        return self.global_index.get_nodes_for_terms(terms)
    
    def locate_term(self, term: str) -> Set[int]:
        """
        Localiza qué nodos contienen un término específico.
        
        Args:
            term: Término a buscar
            
        Returns:
            Conjunto de node_ids que contienen el término
        """
        return self.global_index.get_nodes_for_term(term)
    
    def get_active_nodes(self) -> Set[int]:
        """Retorna los nodos activos."""
        return self.node_registry.get_active_nodes()
    
    def heartbeat(self, node_id: int, doc_count: int = None, term_count: int = None):
        """
        Procesa heartbeat de un nodo.
        
        Args:
            node_id: ID del nodo
            doc_count: Número de documentos (opcional)
            term_count: Número de términos (opcional)
        """
        self.node_registry.heartbeat(node_id)
        
        if doc_count is not None or term_count is not None:
            self.node_registry.update_stats(
                node_id,
                doc_count or 0,
                term_count or 0
            )
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del balancer."""
        return {
            "node_id": self.node_id,
            "global_index": {
                "terms": self.global_index.get_term_count(),
                "nodes": self.global_index.get_node_count()
            },
            "node_registry": {
                "total_nodes": self.node_registry.count(),
                "active_nodes": len(self.node_registry.get_active_nodes()),
                "total_documents": self.node_registry.get_total_documents(),
                "total_terms": self.node_registry.get_total_terms()
            }
        }
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            "global_index": self.global_index.to_dict(),
            "nodes_metadata": self.node_registry.to_dict()
        }
    
    def from_dict(self, data: Dict):
        """Carga desde diccionario."""
        if "global_index" in data:
            self.global_index.from_dict(data["global_index"])
        
        if "nodes_metadata" in data:
            self.node_registry.from_dict(data["nodes_metadata"])
        
        logger.info("DataBalancer: Estado restaurado desde snapshot")

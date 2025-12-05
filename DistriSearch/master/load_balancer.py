"""
DistriSearch Master - Balanceador de carga

Distribuye queries y asigna documentos a Slaves
basándose en afinidad semántica y carga actual.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import random

from ..core.models import NodeInfo, NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class NodeLoad:
    """Estado de carga de un nodo"""
    node_id: str
    active_queries: int = 0
    cpu_usage: float = 0.0  # 0-100
    memory_usage: float = 0.0  # 0-100
    document_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def load_score(self) -> float:
        """Score de carga combinado (0.0 = libre, 1.0 = sobrecargado)"""
        # Pesos para diferentes métricas
        query_weight = 0.3
        cpu_weight = 0.4
        memory_weight = 0.3
        
        # Normalizar queries activas (asume max 10 queries simultáneas)
        query_load = min(self.active_queries / 10.0, 1.0)
        
        return (
            query_weight * query_load +
            cpu_weight * (self.cpu_usage / 100.0) +
            memory_weight * (self.memory_usage / 100.0)
        )
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "active_queries": self.active_queries,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "document_count": self.document_count,
            "load_score": self.load_score,
            "last_updated": self.last_updated.isoformat()
        }


class LoadBalancer:
    """
    Balanceador de carga para el cluster Master-Slave.
    
    Estrategias de balanceo:
    1. Semántica: Prioriza nodos con contenido similar
    2. Round-robin: Distribución equitativa
    3. Least-connections: Prioriza nodos con menos queries activas
    4. Weighted: Combina semántica + carga
    """
    
    def __init__(self, strategy: str = "weighted"):
        """
        Args:
            strategy: Estrategia de balanceo 
                      ('semantic', 'round_robin', 'least_connections', 'weighted')
        """
        self.strategy = strategy
        
        # Estado de nodos
        self._nodes: Dict[str, NodeInfo] = {}
        self._loads: Dict[str, NodeLoad] = {}
        
        # Para round-robin
        self._rr_index = 0
        
        # Config
        self.stale_threshold = timedelta(seconds=30)  # Datos obsoletos
    
    def register_node(self, node: NodeInfo) -> None:
        """Registra un nodo en el balanceador"""
        self._nodes[node.node_id] = node
        if node.node_id not in self._loads:
            self._loads[node.node_id] = NodeLoad(node_id=node.node_id)
        logger.info(f"Nodo registrado en balanceador: {node.node_id}")
    
    def unregister_node(self, node_id: str) -> None:
        """Elimina un nodo del balanceador"""
        self._nodes.pop(node_id, None)
        self._loads.pop(node_id, None)
        logger.info(f"Nodo eliminado del balanceador: {node_id}")
    
    def update_load(
        self, 
        node_id: str, 
        active_queries: int = None,
        cpu_usage: float = None,
        memory_usage: float = None,
        document_count: int = None
    ) -> None:
        """Actualiza métricas de carga de un nodo"""
        if node_id not in self._loads:
            self._loads[node_id] = NodeLoad(node_id=node_id)
        
        load = self._loads[node_id]
        
        if active_queries is not None:
            load.active_queries = active_queries
        if cpu_usage is not None:
            load.cpu_usage = cpu_usage
        if memory_usage is not None:
            load.memory_usage = memory_usage
        if document_count is not None:
            load.document_count = document_count
        
        load.last_updated = datetime.utcnow()
    
    def increment_queries(self, node_id: str) -> None:
        """Incrementa contador de queries activas"""
        if node_id in self._loads:
            self._loads[node_id].active_queries += 1
    
    def decrement_queries(self, node_id: str) -> None:
        """Decrementa contador de queries activas"""
        if node_id in self._loads:
            self._loads[node_id].active_queries = max(
                0, self._loads[node_id].active_queries - 1
            )
    
    def select_nodes_for_query(
        self,
        semantic_scores: Optional[List[Tuple[str, float]]] = None,
        num_nodes: int = 3,
        exclude: Optional[List[str]] = None
    ) -> List[str]:
        """
        Selecciona nodos para ejecutar una query.
        
        Args:
            semantic_scores: Scores de afinidad semántica (node_id, score)
            num_nodes: Número de nodos a seleccionar
            exclude: Nodos a excluir
            
        Returns:
            Lista de node_ids seleccionados
        """
        exclude = set(exclude or [])
        
        # Filtrar nodos disponibles
        available = [
            node_id for node_id, node in self._nodes.items()
            if node.status == NodeStatus.ONLINE and node_id not in exclude
        ]
        
        if not available:
            return []
        
        if len(available) <= num_nodes:
            return available
        
        # Seleccionar según estrategia
        if self.strategy == "round_robin":
            return self._select_round_robin(available, num_nodes)
        elif self.strategy == "least_connections":
            return self._select_least_connections(available, num_nodes)
        elif self.strategy == "semantic" and semantic_scores:
            return self._select_semantic(semantic_scores, available, num_nodes)
        elif self.strategy == "weighted" and semantic_scores:
            return self._select_weighted(semantic_scores, available, num_nodes)
        else:
            # Fallback a least_connections
            return self._select_least_connections(available, num_nodes)
    
    def select_node_for_document(
        self,
        semantic_score: Optional[List[Tuple[str, float]]] = None,
        exclude: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Selecciona nodo para almacenar un nuevo documento.
        
        Prioriza:
        1. Afinidad semántica (si hay scores)
        2. Menor carga
        3. Menos documentos
        """
        exclude = set(exclude or [])
        
        available = [
            node_id for node_id, node in self._nodes.items()
            if node.status == NodeStatus.ONLINE and node_id not in exclude
        ]
        
        if not available:
            return None
        
        if len(available) == 1:
            return available[0]
        
        # Calcular score combinado para cada nodo
        node_scores = []
        
        # Convertir semantic_scores a dict
        semantic_dict = {}
        if semantic_score:
            semantic_dict = {node_id: score for node_id, score in semantic_score}
        
        for node_id in available:
            load = self._loads.get(node_id, NodeLoad(node_id=node_id))
            
            # Score de carga (invertido: menor carga = mayor score)
            load_score = 1.0 - load.load_score
            
            # Score de documentos (invertido: menos docs = mayor score)
            max_docs = max(l.document_count for l in self._loads.values()) or 1
            doc_score = 1.0 - (load.document_count / max_docs)
            
            # Score semántico
            sem_score = semantic_dict.get(node_id, 0.5)
            
            # Score combinado
            combined = (0.4 * sem_score + 0.4 * load_score + 0.2 * doc_score)
            node_scores.append((node_id, combined))
        
        # Seleccionar mejor nodo
        node_scores.sort(key=lambda x: x[1], reverse=True)
        return node_scores[0][0]
    
    def _select_round_robin(self, available: List[str], num: int) -> List[str]:
        """Selección round-robin"""
        available = sorted(available)  # Orden consistente
        selected = []
        
        for _ in range(num):
            self._rr_index = (self._rr_index + 1) % len(available)
            selected.append(available[self._rr_index])
        
        return list(set(selected))  # Eliminar duplicados
    
    def _select_least_connections(self, available: List[str], num: int) -> List[str]:
        """Selección por menor número de conexiones activas"""
        loads = [
            (node_id, self._loads.get(node_id, NodeLoad(node_id=node_id)).active_queries)
            for node_id in available
        ]
        loads.sort(key=lambda x: x[1])
        return [node_id for node_id, _ in loads[:num]]
    
    def _select_semantic(
        self, 
        semantic_scores: List[Tuple[str, float]], 
        available: List[str], 
        num: int
    ) -> List[str]:
        """Selección puramente semántica"""
        available_set = set(available)
        filtered = [
            (node_id, score) 
            for node_id, score in semantic_scores 
            if node_id in available_set
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in filtered[:num]]
    
    def _select_weighted(
        self, 
        semantic_scores: List[Tuple[str, float]], 
        available: List[str], 
        num: int
    ) -> List[str]:
        """
        Selección ponderada: combina afinidad semántica con carga.
        
        Score = 0.6 * semantic + 0.4 * (1 - load_score)
        """
        available_set = set(available)
        semantic_dict = {
            node_id: score 
            for node_id, score in semantic_scores 
            if node_id in available_set
        }
        
        weighted_scores = []
        for node_id in available:
            sem_score = semantic_dict.get(node_id, 0.5)
            load = self._loads.get(node_id, NodeLoad(node_id=node_id))
            
            # Penalizar por datos obsoletos
            if datetime.utcnow() - load.last_updated > self.stale_threshold:
                load_score = 0.5  # Asumir carga media si datos obsoletos
            else:
                load_score = 1.0 - load.load_score
            
            weighted = 0.6 * sem_score + 0.4 * load_score
            weighted_scores.append((node_id, weighted))
        
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in weighted_scores[:num]]
    
    def get_node_loads(self) -> Dict[str, NodeLoad]:
        """Retorna estado de carga de todos los nodos"""
        return self._loads.copy()
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del balanceador"""
        total_queries = sum(l.active_queries for l in self._loads.values())
        avg_load = sum(l.load_score for l in self._loads.values()) / len(self._loads) if self._loads else 0
        
        return {
            "strategy": self.strategy,
            "registered_nodes": len(self._nodes),
            "total_active_queries": total_queries,
            "average_load": avg_load,
            "node_loads": {
                node_id: load.to_dict() 
                for node_id, load in self._loads.items()
            }
        }

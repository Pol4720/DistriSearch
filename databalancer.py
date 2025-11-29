"""
Data Balancer: líder replicado que mantiene el índice global.
"""
import asyncio
import json
import logging
import os
from collections import defaultdict
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NodeMetadata:
    """Metadatos de un nodo registrado."""
    node_id: int
    endpoint: str  # host:port o identificador
    capacity: int = 100  # Capacidad relativa
    last_heartbeat: float = 0.0
    terms: Set[str] = None  # Términos que el nodo tiene
    
    def __post_init__(self):
        if self.terms is None:
            self.terms = set()


@dataclass
class IndexUpdate:
    """Actualización del índice global."""
    node_id: int
    terms_added: List[str]
    terms_removed: List[str]
    timestamp: float


class GlobalIndex:
    """
    Índice global: término -> conjunto de nodos que lo tienen.
    
    Mantenido por el Data Balancer (líder).
    """
    
    def __init__(self, persist_path: str = "data/balancer"):
        self.persist_path = persist_path
        
        # término -> set(node_ids)
        self.term_to_nodes: Dict[str, Set[int]] = defaultdict(set)
        
        # node_id -> NodeMetadata
        self.nodes: Dict[int, NodeMetadata] = {}
        
        os.makedirs(persist_path, exist_ok=True)
        self.load()
    
    def register_node(self, node_id: int, endpoint: str, capacity: int = 100):
        """Registra un nuevo nodo."""
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeMetadata(
                node_id=node_id,
                endpoint=endpoint,
                capacity=capacity,
                last_heartbeat=asyncio.get_event_loop().time(),
                terms=set()
            )
        else:
            # Actualizar endpoint y heartbeat
            self.nodes[node_id].endpoint = endpoint
            self.nodes[node_id].capacity = capacity
            self.nodes[node_id].last_heartbeat = asyncio.get_event_loop().time()
        
        logger.info(f"Nodo {node_id} registrado en índice global")
    
    def update_heartbeat(self, node_id: int):
        """Actualiza timestamp de heartbeat de un nodo."""
        if node_id in self.nodes:
            self.nodes[node_id].last_heartbeat = asyncio.get_event_loop().time()
    
    def apply_update(self, update: IndexUpdate):
        """
        Aplica una actualización al índice global.
        
        Args:
            update: Actualización a aplicar
        """
        node_id = update.node_id
        
        if node_id not in self.nodes:
            logger.warning(f"Actualización de nodo desconocido: {node_id}")
            return
        
        # Añadir términos
        for term in update.terms_added:
            self.term_to_nodes[term].add(node_id)
            self.nodes[node_id].terms.add(term)
        
        # Remover términos
        for term in update.terms_removed:
            if term in self.term_to_nodes:
                self.term_to_nodes[term].discard(node_id)
                if not self.term_to_nodes[term]:
                    del self.term_to_nodes[term]
            self.nodes[node_id].terms.discard(term)
        
        logger.debug(f"Índice actualizado: +{len(update.terms_added)}, -{len(update.terms_removed)} términos")
    
    def locate_term(self, term: str) -> List[int]:
        """
        Encuentra qué nodos contienen un término.
        
        Args:
            term: Término a buscar
        
        Returns:
            Lista de node_ids que contienen el término
        """
        return list(self.term_to_nodes.get(term, set()))
    
    def get_node_metadata(self, node_id: int) -> Optional[NodeMetadata]:
        """Obtiene metadatos de un nodo."""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[int]:
        """Retorna todos los nodos registrados."""
        return list(self.nodes.keys())
    
    def remove_node(self, node_id: int):
        """Elimina un nodo del índice (por timeout o fallo)."""
        if node_id not in self.nodes:
            return
        
        # Remover de term_to_nodes
        for term in self.nodes[node_id].terms:
            if term in self.term_to_nodes:
                self.term_to_nodes[term].discard(node_id)
                if not self.term_to_nodes[term]:
                    del self.term_to_nodes[term]
        
        del self.nodes[node_id]
        logger.info(f"Nodo {node_id} eliminado del índice global")
    
    def save(self):
        """Persiste el índice global."""
        index_file = os.path.join(self.persist_path, "global_index.json")
        nodes_file = os.path.join(self.persist_path, "nodes_metadata.json")
        
        try:
            # Guardar term_to_nodes (convertir sets a listas)
            term_data = {term: list(nodes) for term, nodes in self.term_to_nodes.items()}
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(term_data, f, ensure_ascii=False, indent=2)
            
            # Guardar metadatos de nodos
            nodes_data = {}
            for node_id, metadata in self.nodes.items():
                data = asdict(metadata)
                data['terms'] = list(data['terms'])  # Convertir set a lista
                nodes_data[str(node_id)] = data
            
            with open(nodes_file, 'w', encoding='utf-8') as f:
                json.dump(nodes_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Índice global guardado en {self.persist_path}")
        except Exception as e:
            logger.error(f"Error guardando índice global: {e}")
    
    def load(self):
        """Carga el índice global desde disco."""
        index_file = os.path.join(self.persist_path, "global_index.json")
        nodes_file = os.path.join(self.persist_path, "nodes_metadata.json")
        
        try:
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    term_data = json.load(f)
                    self.term_to_nodes = defaultdict(set, {
                        term: set(nodes) for term, nodes in term_data.items()
                    })
            
            if os.path.exists(nodes_file):
                with open(nodes_file, 'r', encoding='utf-8') as f:
                    nodes_data = json.load(f)
                    for node_id_str, data in nodes_data.items():
                        data['terms'] = set(data['terms'])
                        data['node_id'] = int(node_id_str)
                        self.nodes[int(node_id_str)] = NodeMetadata(**data)
            
            logger.info(f"Índice global cargado: {len(self.term_to_nodes)} términos")
        except Exception as e:
            logger.warning(f"Error cargando índice global: {e}")
    
    def get_snapshot(self) -> Dict:
        """Retorna snapshot del estado completo para replicación."""
        return {
            'term_to_nodes': {term: list(nodes) for term, nodes in self.term_to_nodes.items()},
            'nodes': {
                str(node_id): {
                    **asdict(metadata),
                    'terms': list(metadata.terms)
                }
                for node_id, metadata in self.nodes.items()
            }
        }
    
    def restore_snapshot(self, snapshot: Dict):
        """Restaura el estado desde un snapshot."""
        try:
            self.term_to_nodes = defaultdict(set, {
                term: set(nodes) for term, nodes in snapshot['term_to_nodes'].items()
            })
            
            self.nodes = {}
            for node_id_str, data in snapshot['nodes'].items():
                data['terms'] = set(data['terms'])
                data['node_id'] = int(node_id_str)
                self.nodes[int(node_id_str)] = NodeMetadata(**data)
            
            logger.info(f"Snapshot restaurado: {len(self.term_to_nodes)} términos")
        except Exception as e:
            logger.error(f"Error restaurando snapshot: {e}")


class DataBalancer:
    """
    Data Balancer: coordina el índice global y la localización de términos.
    
    Puede ser líder (activo) o follower (réplica).
    """
    
    def __init__(self, node_id: int, is_leader: bool = False, 
                 persist_path: str = None):
        """
        Inicializa el Data Balancer.
        
        Args:
            node_id: ID de este nodo balanceador
            is_leader: Si es líder activo
            persist_path: Ruta para persistencia
        """
        self.node_id = node_id
        self.is_leader = is_leader
        
        self.global_index = GlobalIndex(persist_path or f"data/balancer_{node_id}")
        
        # Followers conocidos (si soy líder)
        self.followers: Set[int] = set()
        
        # Líder conocido (si soy follower)
        self.leader_id: Optional[int] = None
        
        # Heartbeat config
        self.heartbeat_interval = 2.0  # segundos
        self.heartbeat_timeout = 6.0  # segundos
        
        # Snapshot config
        self.snapshot_interval = 30.0  # segundos
        
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
    
    def become_leader(self):
        """Promueve este balancer a líder."""
        if self.is_leader:
            return
        
        logger.info(f"DataBalancer {self.node_id}: promovido a LÍDER")
        self.is_leader = True
        self.leader_id = self.node_id
        
        # Iniciar tareas de líder
        self._start_leader_tasks()
    
    def become_follower(self, leader_id: int):
        """Degrada este balancer a follower."""
        if not self.is_leader:
            return
        
        logger.info(f"DataBalancer {self.node_id}: degradado a FOLLOWER (líder: {leader_id})")
        self.is_leader = False
        self.leader_id = leader_id
        
        # Detener tareas de líder
        self._stop_leader_tasks()
    
    def _start_leader_tasks(self):
        """Inicia tareas periódicas del líder."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        if self._snapshot_task is None or self._snapshot_task.done():
            self._snapshot_task = asyncio.create_task(self._snapshot_loop())
    
    def _stop_leader_tasks(self):
        """Detiene tareas periódicas del líder."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        
        if self._snapshot_task and not self._snapshot_task.done():
            self._snapshot_task.cancel()
    
    async def _heartbeat_loop(self):
        """Loop de heartbeat (solo líder)."""
        while self.is_leader:
            try:
                # Verificar timeouts de nodos
                current_time = asyncio.get_event_loop().time()
                dead_nodes = []
                
                for node_id, metadata in self.global_index.nodes.items():
                    if current_time - metadata.last_heartbeat > self.heartbeat_timeout:
                        dead_nodes.append(node_id)
                
                for node_id in dead_nodes:
                    logger.warning(f"Nodo {node_id} timeout, eliminando")
                    self.global_index.remove_node(node_id)
                
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en heartbeat loop: {e}")
                await asyncio.sleep(1)
    
    async def _snapshot_loop(self):
        """Loop de guardado de snapshots (solo líder)."""
        while self.is_leader:
            try:
                await asyncio.sleep(self.snapshot_interval)
                self.global_index.save()
                logger.debug("Snapshot del índice global guardado")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en snapshot loop: {e}")
    
    # API del Data Balancer
    
    def handle_register_node(self, node_id: int, endpoint: str, capacity: int = 100) -> Dict:
        """Maneja POST /register_node."""
        if not self.is_leader:
            return {'error': 'Not leader', 'leader_id': self.leader_id}
        
        self.global_index.register_node(node_id, endpoint, capacity)
        
        return {'status': 'ok', 'node_id': node_id}
    
    def handle_update_index(self, node_id: int, terms_added: List[str], 
                           terms_removed: List[str]) -> Dict:
        """Maneja POST /update_index."""
        if not self.is_leader:
            return {'error': 'Not leader', 'leader_id': self.leader_id}
        
        update = IndexUpdate(
            node_id=node_id,
            terms_added=terms_added,
            terms_removed=terms_removed,
            timestamp=asyncio.get_event_loop().time()
        )
        
        self.global_index.apply_update(update)
        
        return {'status': 'ok', 'timestamp': update.timestamp}
    
    def handle_locate(self, term: str) -> Dict:
        """Maneja GET /locate?q=term."""
        nodes = self.global_index.locate_term(term)
        
        # Incluir endpoints
        node_info = []
        for node_id in nodes:
            metadata = self.global_index.get_node_metadata(node_id)
            if metadata:
                node_info.append({
                    'node_id': node_id,
                    'endpoint': metadata.endpoint
                })
        
        return {'term': term, 'nodes': node_info}
    
    def handle_heartbeat(self, node_id: int) -> Dict:
        """Maneja POST /heartbeat."""
        if not self.is_leader:
            return {'error': 'Not leader', 'leader_id': self.leader_id}
        
        self.global_index.update_heartbeat(node_id)
        
        return {'status': 'ok', 'leader_id': self.node_id}
    
    def get_snapshot(self) -> Dict:
        """Retorna snapshot para replicación."""
        return self.global_index.get_snapshot()
    
    def restore_snapshot(self, snapshot: Dict):
        """Restaura desde snapshot."""
        self.global_index.restore_snapshot(snapshot)
    
    async def shutdown(self):
        """Cierra el balancer limpiamente."""
        self._stop_leader_tasks()
        
        if self.is_leader:
            self.global_index.save()
        
        logger.info(f"DataBalancer {self.node_id} apagado")

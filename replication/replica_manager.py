"""
Gestión de réplicas de documentos.
"""
import asyncio
import logging
from typing import Set, List, Dict, Any, Optional
from replication.quorum import QuorumConfig, verify_quorum

logger = logging.getLogger(__name__)


class ReplicaManager:
    """Gestiona la replicación de documentos entre nodos."""
    
    def __init__(
        self,
        node_id: int,
        network,
        hypercube,
        config: QuorumConfig = None
    ):
        """
        Inicializa el gestor de réplicas.
        
        Args:
            node_id: ID de este nodo
            network: Interfaz de red
            hypercube: Topología hipercubo
            config: Configuración de quorum
        """
        self.node_id = node_id
        self.network = network
        self.hypercube = hypercube
        self.config = config or QuorumConfig()
        
        logger.info(
            f"ReplicaManager {node_id}: k={self.config.replication_factor}, "
            f"quorum={self.config.write_quorum}"
        )
        
        # Active nodes cache
        self.active_nodes: Set[int] = set()
    
    def update_active_nodes(self, nodes: List[int]):
        """
        Actualiza lista de nodos activos.
        
        Args:
            nodes: Lista de IDs de nodos activos
        """
        self.active_nodes = set(nodes)
        logger.debug(f"ReplicaManager {self.node_id}: {len(self.active_nodes)} nodos activos")
    
    def select_replica_nodes(self, doc_id: str) -> List[int]:
        """
        Selecciona nodos réplica para un documento.
        
        Estrategia: Vecinos XOR más cercanos para fault tolerance.
        
        Args:
            doc_id: ID del documento
            
        Returns:
            Lista de node_ids (incluye este nodo)
        """
        # Incluir este nodo
        replicas = [self.node_id]
        
        # Seleccionar vecinos más cercanos
        neighbors = self.hypercube.get_neighbors(self.node_id)
        
        # Ordenar por distancia XOR (más cercanos primero)
        sorted_neighbors = sorted(
            neighbors,
            key=lambda n: bin(n ^ self.node_id).count('1')
        )
        
        # Tomar k-1 vecinos adicionales
        needed = self.config.replication_factor - 1
        replicas.extend(sorted_neighbors[:needed])
        
        return replicas[:self.config.replication_factor]
    
    async def replicate_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict = None,
        timeout: float = 5.0
    ) -> tuple[bool, Set[int]]:
        """
        Replica un documento a múltiples nodos.
        
        Args:
            doc_id: ID del documento
            content: Contenido del documento
            metadata: Metadata opcional
            timeout: Timeout en segundos
            
        Returns:
            (success, successful_nodes) donde:
            - success: True si se alcanzó quorum
            - successful_nodes: Conjunto de nodos que replicaron exitosamente
        """
        # Seleccionar nodos réplica
        replica_nodes = self.select_replica_nodes(doc_id)
        
        logger.debug(
            f"ReplicaManager {self.node_id}: Replicando '{doc_id}' a {replica_nodes}"
        )
        
        # Este nodo siempre tiene éxito
        successful = {self.node_id}
        
        # Enviar a otros nodos en paralelo
        tasks = []
        other_nodes = [n for n in replica_nodes if n != self.node_id]
        
        for node_id in other_nodes:
            task = self._send_replica(
                node_id,
                doc_id,
                content,
                metadata,
                timeout
            )
            tasks.append(task)
        
        # Esperar respuestas
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Contar éxitos
        for node_id, result in zip(other_nodes, results):
            if result is True:
                successful.add(node_id)
        
        # Verificar quorum
        success = verify_quorum(
            successful,
            self.config.write_quorum,
            self.config.replication_factor
        )
        
        logger.info(
            f"ReplicaManager {self.node_id}: '{doc_id}' replicado a "
            f"{len(successful)}/{self.config.replication_factor} nodos "
            f"({'OK' if success else 'FALLO'})"
        )
        
        return success, successful
    
    async def _send_replica(
        self,
        node_id: int,
        doc_id: str,
        content: str,
        metadata: Dict,
        timeout: float
    ) -> bool:
        """
        Envía réplica a un nodo.
        
        Returns:
            True si exitoso, False en caso contrario
        """
        try:
            message = {
                "type": "replicate_document",
                "payload": {
                    "doc_id": doc_id,
                    "content": content,
                    "metadata": metadata or {}
                }
            }
            
            response = await self.network.send_message(
                self.node_id,
                node_id,
                message,
                timeout=timeout
            )
            
            if response and response.get("success"):
                return True
            else:
                logger.warning(
                    f"Nodo {node_id} rechazó réplica de '{doc_id}'"
                )
                return False
                
        except Exception as e:
            logger.error(
                f"Error replicando '{doc_id}' a nodo {node_id}: {e}"
            )
            return False
    
    async def delete_replicas(
        self,
        doc_id: str,
        replica_nodes: List[int],
        timeout: float = 5.0
    ) -> Set[int]:
        """
        Elimina réplicas de un documento (para rollback).
        
        Args:
            doc_id: ID del documento
            replica_nodes: Nodos donde eliminar
            timeout: Timeout en segundos
            
        Returns:
            Conjunto de nodos donde se eliminó exitosamente
        """
        tasks = []
        
        for node_id in replica_nodes:
            if node_id != self.node_id:
                task = self._delete_replica(node_id, doc_id, timeout)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = {self.node_id}  # Asumimos éxito local
        for node_id, result in zip(replica_nodes, results):
            if result is True:
                successful.add(node_id)
        
        return successful
    
    async def _delete_replica(
        self,
        node_id: int,
        doc_id: str,
        timeout: float
    ) -> bool:
        """Elimina réplica en un nodo."""
        try:
            message = {
                "type": "delete_document",
                "payload": {"doc_id": doc_id}
            }
            
            response = await self.network.send_message(
                self.node_id,
                node_id,
                message,
                timeout=timeout
            )
            
            return response and response.get("success")
            
        except Exception as e:
            logger.error(
                f"Error eliminando réplica de '{doc_id}' en nodo {node_id}: {e}"
            )
            return False

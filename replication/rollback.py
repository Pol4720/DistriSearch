"""
Gestión de rollback de transacciones.
"""
import logging
from typing import Set, List

logger = logging.getLogger(__name__)


class RollbackManager:
    """Gestiona el rollback de operaciones fallidas."""
    
    def __init__(self, replica_manager):
        """
        Inicializa el gestor de rollback.
        
        Args:
            replica_manager: Instancia de ReplicaManager
        """
        self.replica_manager = replica_manager
    
    async def rollback_replication(
        self,
        doc_id: str,
        successful_nodes: Set[int],
        timeout: float = 3.0
    ) -> int:
        """
        Hace rollback de una replicación fallida.
        
        Elimina el documento de los nodos donde se replicó exitosamente.
        
        Args:
            doc_id: ID del documento
            successful_nodes: Nodos donde se replicó
            timeout: Timeout en segundos
            
        Returns:
            Número de nodos donde se hizo rollback exitosamente
        """
        logger.warning(
            f"RollbackManager: Iniciando rollback de '{doc_id}' "
            f"en {len(successful_nodes)} nodos"
        )
        
        # Eliminar de nodos exitosos
        deleted = await self.replica_manager.delete_replicas(
            doc_id,
            list(successful_nodes),
            timeout=timeout
        )
        
        logger.info(
            f"RollbackManager: Rollback de '{doc_id}' completado "
            f"({len(deleted)}/{len(successful_nodes)} nodos)"
        )
        
        return len(deleted)
    
    async def rollback_multiple(
        self,
        operations: List[tuple],
        timeout: float = 3.0
    ) -> int:
        """
        Hace rollback de múltiples operaciones.
        
        Args:
            operations: Lista de (doc_id, successful_nodes)
            timeout: Timeout en segundos
            
        Returns:
            Número total de rollbacks exitosos
        """
        total_rolled_back = 0
        
        for doc_id, successful_nodes in operations:
            count = await self.rollback_replication(
                doc_id,
                successful_nodes,
                timeout
            )
            total_rolled_back += count
        
        return total_rolled_back

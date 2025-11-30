"""
Módulo de replicación de documentos.
Maneja la replicación distribuida de documentos con quorum.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NodeReplication:
    """
    Mixin que añade capacidades de replicación al nodo.
    Requiere que la clase tenga: node_id, storage, replication, route_message
    """
    
    async def add_document(
        self, 
        doc_id: str, 
        content: str, 
        metadata: Dict = None
    ) -> Dict:
        """
        Añade un documento CON REPLICACIÓN distribuida.
        
        Algoritmo:
        1. Determinar nodos réplica usando consistent hashing
        2. Si soy réplica: indexar localmente
        3. Si no soy réplica: redirigir al nodo primario
        4. Replicar en paralelo a otros nodos réplica
        5. Esperar quorum (k/2 + 1)
        6. Si no hay quorum: rollback
        7. Notificar al Data Balancer (solo primario)
        
        Args:
            doc_id: ID único del documento
            content: Contenido textual del documento
            metadata: Metadatos opcionales
            
        Returns:
            Dict con status, replicas exitosas, términos indexados
        """
        logger.info(f"Nodo {self.node_id}: Añadiendo documento {doc_id}")
        
        # 1. Determinar nodos réplica (k=3)
        replica_nodes = self.replication.get_replica_nodes(doc_id)
        logger.debug(f"Réplicas para {doc_id}: {replica_nodes}")
        
        # 2. Indexar SOLO si soy una réplica
        if self.node_id in replica_nodes:
            terms_added = self.storage.add_document(doc_id, content, metadata)
            self.storage.save()
            logger.info(
                f"Documento {doc_id} indexado localmente: "
                f"{len(terms_added)} términos"
            )
        else:
            # Si no soy réplica, redirijo al nodo primario
            primary_node = replica_nodes[0] if replica_nodes else self.node_id
            if primary_node != self.node_id:
                logger.info(
                    f"Redirigiendo {doc_id} al nodo primario {primary_node}"
                )
                response = await self.route_message(
                    primary_node,
                    {
                        "type": "add_doc_primary",
                        "doc_id": doc_id,
                        "content": content,
                        "metadata": metadata
                    }
                )
                return response if response else {
                    "status": "error", 
                    "message": "Redirección falló"
                }
            terms_added = set()
        
        # 3. Replicar a OTROS nodos réplica (en paralelo)
        replication_tasks = []
        successful_replicas = (
            [self.node_id] if self.node_id in replica_nodes else []
        )
        
        for replica_id in replica_nodes:
            if replica_id != self.node_id:
                task = self._replicate_document(
                    replica_id, doc_id, content, metadata
                )
                replication_tasks.append((replica_id, task))
        
        # 4. Esperar replicaciones (con timeout)
        if replication_tasks:
            for replica_id, task in replication_tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=5.0)
                    if result:
                        successful_replicas.append(replica_id)
                        logger.debug(f"Replicación a {replica_id}: OK")
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout replicando a {replica_id}")
                except Exception as e:
                    logger.error(f"Error replicando a {replica_id}: {e}")
        
        # 5. Verificar quorum (k/2 + 1)
        replication_factor = self.replication.replication_factor
        quorum = (replication_factor // 2) + 1
        
        if len(successful_replicas) < quorum:
            logger.error(
                f"Quorum NO alcanzado para {doc_id}: "
                f"{len(successful_replicas)}/{replication_factor} réplicas"
            )
            # Rollback: eliminar documento de réplicas exitosas
            await self._rollback_replication(doc_id, successful_replicas)
            
            return {
                "status": "error",
                "message": "Quorum de replicación no alcanzado",
                "successful_replicas": len(successful_replicas),
                "required": quorum
            }
        
        # 6. Notificar al Data Balancer (solo el primario)
        if (self.node_id in replica_nodes and 
            self.replication.is_primary_replica(doc_id, self.node_id)):
            # Notificar a TODOS los coordinadores de shard
            await self._notify_shard_coordinators(list(terms_added), [])
        
        logger.info(
            f"Documento {doc_id} replicado: "
            f"{len(successful_replicas)}/{replication_factor} réplicas"
        )
        
        return {
            "status": "ok",
            "doc_id": doc_id,
            "replicas": successful_replicas,
            "terms_indexed": (
                len(terms_added) if self.node_id in replica_nodes else 0
            )
        }
    
    async def _replicate_document(
        self, 
        target_node: int, 
        doc_id: str, 
        content: str, 
        metadata: Dict
    ) -> bool:
        """
        Replica documento a un nodo específico.
        
        Args:
            target_node: ID del nodo destino
            doc_id: ID del documento
            content: Contenido del documento
            metadata: Metadatos
            
        Returns:
            True si replicación exitosa, False si no
        """
        try:
            response = await self.route_message(
                target_node,
                {
                    "type": "replicate_doc",
                    "doc_id": doc_id,
                    "content": content,
                    "metadata": metadata,
                    "source_node": self.node_id
                }
            )
            return response.get("status") == "ok" if response else False
        except Exception as e:
            logger.error(f"Error replicando a {target_node}: {e}")
            return False
    
    async def _rollback_replication(
        self, 
        doc_id: str, 
        successful_replicas: List[int]
    ):
        """
        Hace rollback de documento en réplicas exitosas.
        Se usa cuando no se alcanza quorum.
        
        Args:
            doc_id: ID del documento a eliminar
            successful_replicas: Lista de nodos que tienen el documento
        """
        logger.warning(f"Haciendo rollback de documento {doc_id}")
        
        for replica_id in successful_replicas:
            if replica_id == self.node_id:
                # Rollback local
                self.storage.remove_document(doc_id)
                self.storage.save()
            else:
                # Rollback remoto
                await self._send_rollback(replica_id, doc_id)
    
    async def _send_rollback(self, target_node: int, doc_id: str):
        """
        Envía mensaje de rollback a réplica remota.
        
        Args:
            target_node: ID del nodo destino
            doc_id: ID del documento a eliminar
        """
        try:
            await self.route_message(
                target_node,
                {
                    "type": "rollback_doc",
                    "doc_id": doc_id
                }
            )
        except Exception as e:
            logger.error(f"Error en rollback a {target_node}: {e}")
    
    async def handle_replicate_doc(self, message: Dict) -> Dict:
        """
        Maneja mensaje de replicación de documento.
        
        Args:
            message: Mensaje con doc_id, content, metadata, source_node
            
        Returns:
            Dict con status y términos indexados
        """
        doc_id = message.get('doc_id')
        content = message.get('content')
        metadata = message.get('metadata')
        source_node = message.get('source_node')
        
        logger.info(f"Replicando documento {doc_id} desde nodo {source_node}")
        
        try:
            terms_added = self.storage.add_document(doc_id, content, metadata)
            self.storage.save()
            
            return {
                "status": "ok",
                "terms_indexed": len(terms_added)
            }
        except Exception as e:
            logger.error(f"Error replicando documento {doc_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def handle_rollback_doc(self, message: Dict) -> Dict:
        """
        Maneja mensaje de rollback de documento.
        
        Args:
            message: Mensaje con doc_id
            
        Returns:
            Dict con status ok
        """
        doc_id = message.get('doc_id')
        logger.warning(f"Rollback de documento {doc_id}")
        
        self.storage.remove_document(doc_id)
        self.storage.save()
        
        return {"status": "ok"}
    
    async def handle_add_doc_primary(self, message: Dict) -> Dict:
        """
        Maneja redirección de documento al nodo primario.
        
        Args:
            message: Mensaje con doc_id, content, metadata
            
        Returns:
            Resultado de add_document
        """
        doc_id = message.get('doc_id')
        content = message.get('content')
        metadata = message.get('metadata')
        
        return await self.add_document(doc_id, content, metadata)

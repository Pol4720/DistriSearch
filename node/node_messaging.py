"""
Módulo de mensajería y ruteo.
Maneja el ruteo de mensajes por el hipercubo y despacho de mensajes.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Dict, Any, Optional, List

from core.routing import HypercubeRouter

logger = logging.getLogger(__name__)


class NodeMessaging:
    """
    Mixin que añade capacidades de mensajería al nodo.
    Requiere que la clase tenga: node_id, hypercube, known_neighbors,
    dimensions, network, consensus, data_balancer
    """
    
    async def route_message(
        self, 
        dest_id: int, 
        message: Dict[str, Any], 
        hop_limit: int = 32
    ) -> Optional[Dict[str, Any]]:
        """
        Rutea un mensaje al nodo destino usando el hipercubo.
        
        Args:
            dest_id: ID del nodo destino
            message: Mensaje a enviar
            hop_limit: Límite de saltos para evitar loops
            
        Returns:
            Respuesta del nodo destino, o None si falla
        """
        if hop_limit <= 0:
            logger.warning(f"Límite de saltos alcanzado en nodo {self.node_id}")
            return None
        
        if dest_id == self.node_id:
            return await self.handle_message(message)
        
        # Calcular siguiente salto usando router
        router = HypercubeRouter(self.dimensions)
        next_hop = router.route_next_hop(
            self.node_id, dest_id, self.known_neighbors
        )
        
        if next_hop is None:
            logger.error(f"No hay ruta de {self.node_id} a {dest_id}")
            return None
        
        # Reenviar mensaje
        route_envelope = {
            'type': 'route',
            'dest_id': dest_id,
            'hop_limit': hop_limit - 1,
            'payload': message
        }
        
        try:
            return await self._send_to_node(next_hop, route_envelope)
        except Exception as e:
            logger.error(f"Error ruteando a {dest_id} vía {next_hop}: {e}")
            return None
    
    async def _send_to_node(
        self, 
        dest_id: int, 
        message: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Envía mensaje a otro nodo directamente.
        
        Args:
            dest_id: ID del nodo destino
            message: Mensaje a enviar
            
        Returns:
            Respuesta del nodo, o None si falla
        """
        try:
            return await self.network.send_message(
                self.node_id, dest_id, message
            )
        except Exception as e:
            logger.debug(f"Error enviando a nodo {dest_id}: {e}")
            return None
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja un mensaje recibido despachándolo al handler apropiado.
        
        Args:
            message: Mensaje con campo 'type' que determina el handler
            
        Returns:
            Respuesta del handler
        """
        msg_type = message.get('type')
        
        # Ruteo
        if msg_type == 'route':
            return await self._handle_route(message)
        
        # Consenso Raft
        elif msg_type == 'raft_message':
            return await self._handle_raft_message(message)
        
        # Búsqueda
        elif msg_type == 'search_local':
            return self.handle_search_local(message)
        
        # Replicación de documentos
        elif msg_type == 'replicate_doc':
            return await self.handle_replicate_doc(message)
        
        elif msg_type == 'rollback_doc':
            return await self.handle_rollback_doc(message)
        
        elif msg_type == 'add_doc_primary':
            return await self.handle_add_doc_primary(message)
        
        # Sharding
        elif msg_type == 'update_shard':
            return await self._handle_update_shard(message)
        
        elif msg_type == 'balancer_update':
            return await self._handle_balancer_update(message)
        
        elif msg_type == 'locate_term':
            return self._handle_locate_term(message)
        
        # Utilidades
        elif msg_type == 'ping':
            return {'type': 'pong', 'node_id': self.node_id}
        
        elif msg_type == 'cache_invalidate':
            return self._handle_cache_invalidate(message)
        
        else:
            logger.warning(f"Tipo de mensaje desconocido: {msg_type}")
            return {'error': 'unknown_message_type'}
    
    async def _handle_route(self, message: Dict) -> Dict:
        """Maneja mensaje de ruteo."""
        dest_id = message.get('dest_id')
        hop_limit = message.get('hop_limit', 32)
        payload = message.get('payload')
        return await self.route_message(dest_id, payload, hop_limit)
    
    async def _handle_raft_message(self, message: Dict) -> Dict:
        """Maneja mensaje de consenso Raft."""
        await self.consensus.handle_raft_message(message)
        return {'status': 'ok'}
    
    async def _handle_update_shard(self, message: Dict) -> Dict:
        """
        Maneja actualización de shard local.
        
        Args:
            message: {node_id, terms_added, terms_removed}
        """
        node_id = message.get('node_id')
        terms_added = message.get('terms_added', [])
        terms_removed = message.get('terms_removed', [])
        
        # Actualizar shard manager local
        for term in terms_added:
            self.data_balancer.shard_manager.add_term_to_local_shard(
                term, node_id
            )
        
        for term in terms_removed:
            self.data_balancer.shard_manager.remove_term_from_local_shard(
                term, node_id
            )
        
        logger.debug(
            f"Shard actualizado: +{len(terms_added)}, -{len(terms_removed)} "
            f"términos del nodo {node_id}"
        )
        
        return {"status": "ok"}
    
    async def _handle_balancer_update(self, message: Dict) -> Dict:
        """
        Maneja actualización desde nodo al líder.
        
        Args:
            message: {node_id, terms_added, terms_removed}
        """
        if self.data_balancer.is_leader:
            node_id = message.get('node_id')
            terms_added = message.get('terms_added', [])
            terms_removed = message.get('terms_removed', [])
            
            result = self.data_balancer.handle_update_index(
                node_id, terms_added, terms_removed
            )
            
            return result
        else:
            return {"status": "error", "message": "No soy el líder"}
    
    def _handle_locate_term(self, message: Dict) -> Dict:
        """
        Maneja localización de término en shard local.
        
        Args:
            message: {term}
        """
        term = message.get('term')
        
        if not term:
            return {"status": "error", "message": "Término no especificado"}
        
        try:
            nodes = self.data_balancer.shard_manager.get_nodes_for_term(term)
            return {
                "status": "ok",
                "term": term,
                "nodes": list(nodes)
            }
        except Exception as e:
            logger.error(f"Error localizando término '{term}': {e}")
            return {"status": "error", "message": str(e)}
    
    def _handle_cache_invalidate(self, message: Dict) -> Dict:
        """
        Maneja invalidación de cache.
        
        Args:
            message: {key}
        """
        key = message.get('key')
        self.cache.local_cache.invalidate(key)
        return {'status': 'ok'}
    
    async def _notify_shard_coordinators(
        self, 
        terms_added: List[str], 
        terms_removed: List[str]
    ):
        """
        Notifica a coordinadores de shard sobre cambios en términos.
        
        Args:
            terms_added: Lista de términos añadidos
            terms_removed: Lista de términos eliminados
        """
        if not terms_added and not terms_removed:
            return
        
        # Obtener líder actual
        leader_id = self.consensus.current_leader
        
        if leader_id is None:
            logger.warning("No hay líder, no se puede notificar")
            return
        
        # Si no somos líder, enviar todo al líder
        if leader_id != self.node_id:
            try:
                response = await self.route_message(
                    leader_id,
                    {
                        "type": "balancer_update",
                        "node_id": self.node_id,
                        "terms_added": terms_added,
                        "terms_removed": terms_removed
                    }
                )
                logger.debug(
                    f"Actualización enviada al líder {leader_id}: {response}"
                )
            except Exception as e:
                logger.error(f"Error notificando al líder {leader_id}: {e}")
            
            return
        
        # Si somos el líder, distribuir por shards
        shard_manager = self.data_balancer.shard_manager
        updates_by_coordinator: Dict[int, Dict] = defaultdict(lambda: {
            "terms_added": [],
            "terms_removed": []
        })
        
        for term in terms_added:
            shard_id = shard_manager.get_shard_id(term)
            coordinator = shard_manager.shard_map[shard_id].coordinator_node
            updates_by_coordinator[coordinator]["terms_added"].append(term)
        
        for term in terms_removed:
            shard_id = shard_manager.get_shard_id(term)
            coordinator = shard_manager.shard_map[shard_id].coordinator_node
            updates_by_coordinator[coordinator]["terms_removed"].append(term)
        
        # Enviar actualizaciones a cada coordinador
        for coordinator_id, updates in updates_by_coordinator.items():
            if coordinator_id == self.node_id:
                # Local: actualizar directamente
                for term in updates["terms_added"]:
                    shard_manager.add_term_to_local_shard(term, self.node_id)
                
                for term in updates["terms_removed"]:
                    shard_manager.remove_term_from_local_shard(
                        term, self.node_id
                    )
            else:
                # Remoto: enviar mensaje
                try:
                    await self.route_message(
                        coordinator_id,
                        {
                            "type": "update_shard",
                            "node_id": self.node_id,
                            "terms_added": updates["terms_added"],
                            "terms_removed": updates["terms_removed"]
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Error notificando coordinador {coordinator_id}: {e}"
                    )

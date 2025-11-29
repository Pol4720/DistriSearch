"""
Nodo del buscador distribuido con API HTTP.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from aiohttp import web
import json

from hypercube import HypercubeNode, route_next_hop, generate_node_id
from election import BullyElection, ElectionMessage, MessageType
from storage import InvertedIndex
from databalancer import DataBalancer
from network import NetworkInterface, create_network

logger = logging.getLogger(__name__)


class DistributedNode:
    """
    Nodo del buscador distribuido.
    
    Combina:
    - Topología hipercubo
    - Almacenamiento local (índice invertido)
    - Elección de líder
    - Data Balancer (si es líder)
    - API HTTP
    """
    
    def __init__(self, node_id: int, dimensions: int = 20, 
                 host: str = "localhost", port: int = 8000,
                 network: NetworkInterface = None):
        """
        Inicializa el nodo distribuido.
        
        Args:
            node_id: ID único del nodo
            dimensions: Dimensiones del hipercubo
            host: Host para servidor HTTP
            port: Puerto para servidor HTTP
            network: Interfaz de red (simulated o HTTP)
        """
        self.node_id = node_id
        self.dimensions = dimensions
        self.host = host
        self.port = port
        
        # Componentes
        self.hypercube = HypercubeNode(node_id, dimensions)
        self.storage = InvertedIndex(node_id)
        self.data_balancer = DataBalancer(node_id, is_leader=False)
        
        # Red
        self.network = network or create_network("simulated")
        
        # Vecinos conocidos (subset de vecinos lógicos que están activos)
        self.known_neighbors: Set[int] = set()
        
        # Todos los nodos activos en la red (para elección)
        self.active_nodes: Set[int] = set()
        
        # Elección de líder
        self.election: Optional[BullyElection] = None
        
        # Servidor HTTP (para modo HTTP)
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
    
    async def initialize(self, bootstrap_nodes: List[int] = None):
        """
        Inicializa el nodo y se une a la red.
        
        Args:
            bootstrap_nodes: Lista de nodos conocidos para bootstrap
        """
        # Registrar en la red
        await self.network.register_node(self.node_id, self)
        
        # Actualizar vecinos y nodos activos
        if bootstrap_nodes:
            self.active_nodes.update(bootstrap_nodes)
            self.active_nodes.add(self.node_id)
        else:
            self.active_nodes.add(self.node_id)
        
        # Actualizar vecinos conocidos
        self._update_known_neighbors()
        
        # Inicializar elección
        self.election = BullyElection(
            node_id=self.node_id,
            all_node_ids=self.active_nodes,
            send_message_func=self._send_to_node,
            timeout=3.0
        )
        
        # Si soy el único nodo, me hago líder
        if len(self.active_nodes) == 1:
            self.data_balancer.become_leader()
            self.election.current_leader = self.node_id
        else:
            # Iniciar elección para determinar líder
            leader_id = await self.election.start_election()
            
            if leader_id == self.node_id:
                self.data_balancer.become_leader()
        
        logger.info(f"Nodo {self.node_id} inicializado. Líder: {self.election.current_leader}")
    
    def _update_known_neighbors(self):
        """Actualiza lista de vecinos conocidos que están activos."""
        potential_neighbors = set(self.hypercube.get_neighbors())
        self.known_neighbors = potential_neighbors & self.active_nodes
        
        logger.debug(f"Nodo {self.node_id}: {len(self.known_neighbors)} vecinos activos")
    
    async def _send_to_node(self, dest_id: int, message: Dict[str, Any]):
        """Envía mensaje a otro nodo (usado por elección y ruteo)."""
        try:
            await self.network.send_message(dest_id, message)
        except Exception as e:
            logger.debug(f"Error enviando a nodo {dest_id}: {e}")
            raise
    
    async def route_message(self, dest_id: int, message: Dict[str, Any], 
                           hop_limit: int = 32) -> Optional[Dict[str, Any]]:
        """
        Rutea un mensaje al nodo destino usando el hipercubo.
        
        Args:
            dest_id: ID del nodo destino
            message: Mensaje a enviar
            hop_limit: Límite de saltos
        
        Returns:
            Respuesta del nodo destino
        """
        if hop_limit <= 0:
            logger.error("Hop limit alcanzado en ruteo")
            return None
        
        if dest_id == self.node_id:
            # Mensaje es para mí
            return await self.handle_message(message)
        
        # Calcular siguiente salto
        next_hop = route_next_hop(
            self.node_id, dest_id, self.known_neighbors, self.dimensions
        )
        
        if next_hop is None:
            logger.error(f"No se puede rutear desde {self.node_id} a {dest_id}")
            return None
        
        # Reenviar mensaje
        route_envelope = {
            'type': 'route',
            'dest_id': dest_id,
            'hop_limit': hop_limit - 1,
            'payload': message
        }
        
        try:
            return await self.network.send_message(next_hop, route_envelope)
        except Exception as e:
            logger.error(f"Error ruteando mensaje: {e}")
            return None
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja un mensaje recibido.
        
        Args:
            message: Mensaje a procesar
        
        Returns:
            Respuesta
        """
        msg_type = message.get('type')
        
        if msg_type == 'route':
            # Reenviar mensaje ruteado
            dest_id = message['dest_id']
            hop_limit = message['hop_limit']
            payload = message['payload']
            return await self.route_message(dest_id, payload, hop_limit)
        
        elif msg_type == 'election':
            # Mensaje de elección de líder
            election_msg = ElectionMessage(
                msg_type=MessageType(message['msg_type']),
                sender_id=message['sender_id'],
                election_id=message.get('election_id', 0)
            )
            await self.election.handle_election_message(election_msg)
            return {'status': 'ok'}
        
        elif msg_type == 'search_local':
            # Búsqueda local
            query = message.get('query', '')
            results = self.storage.search(query, top_k=10)
            
            # Convertir a formato serializable
            response_results = []
            for doc_id, score in results:
                doc = self.storage.get_document(doc_id)
                if doc:
                    response_results.append({
                        'doc_id': doc_id,
                        'score': score,
                        'snippet': doc.content[:200]  # Primeros 200 chars
                    })
            
            return {'results': response_results}
        
        elif msg_type == 'ping':
            return {'status': 'ok', 'node_id': self.node_id}
        
        else:
            logger.warning(f"Tipo de mensaje desconocido: {msg_type}")
            return {'error': 'Unknown message type'}
    
    # API pública del nodo
    
    async def add_document(self, doc_id: str, content: str, metadata: Dict = None) -> Dict:
        """
        Añade un documento al índice local.
        
        POST /doc
        """
        terms_added = self.storage.add_document(doc_id, content, metadata)
        self.storage.save()
        
        # Notificar al líder
        if self.election.current_leader is not None:
            try:
                await self._notify_leader_index_update(
                    terms_added=list(terms_added),
                    terms_removed=[]
                )
            except Exception as e:
                logger.warning(f"No se pudo notificar al líder: {e}")
        
        return {
            'status': 'ok',
            'doc_id': doc_id,
            'terms_indexed': len(terms_added)
        }
    
    async def search(self, query: str) -> Dict:
        """
        Realiza búsqueda distribuida.
        
        GET /search?q=...
        
        Flujo:
        1. Consultar al líder qué nodos tienen los términos
        2. Contactar a esos nodos para obtener resultados locales
        3. Agregar y ordenar resultados
        """
        # Tokenizar consulta
        query_terms = self.storage.tokenize(query)
        
        if not query_terms:
            return {'results': [], 'query': query}
        
        # Consultar al líder por cada término
        candidate_nodes = set()
        
        leader_id = self.election.current_leader
        if leader_id is None:
            # No hay líder, solo búsqueda local
            logger.warning("No hay líder, búsqueda solo local")
            local_results = self.storage.search(query, top_k=10)
            return self._format_search_results(local_results, query)
        
        try:
            # Obtener nodos que contienen los términos
            for term in query_terms:
                locate_msg = {
                    'type': 'balancer_locate',
                    'term': term
                }
                
                # Si soy el líder, procesar localmente
                if leader_id == self.node_id:
                    response = self.data_balancer.handle_locate(term)
                else:
                    response = await self.route_message(leader_id, locate_msg)
                
                if response and 'nodes' in response:
                    for node_info in response['nodes']:
                        candidate_nodes.add(node_info['node_id'])
        
        except Exception as e:
            logger.error(f"Error consultando al líder: {e}")
        
        # Siempre incluir búsqueda local
        candidate_nodes.add(self.node_id)
        
        # Recolectar resultados de nodos candidatos
        all_results = []
        
        for node_id in candidate_nodes:
            try:
                if node_id == self.node_id:
                    # Búsqueda local
                    local_results = self.storage.search(query, top_k=10)
                    for doc_id, score in local_results:
                        doc = self.storage.get_document(doc_id)
                        if doc:
                            all_results.append({
                                'doc_id': doc_id,
                                'score': score,
                                'snippet': doc.content[:200],
                                'node_id': self.node_id
                            })
                else:
                    # Búsqueda remota
                    search_msg = {
                        'type': 'search_local',
                        'query': query
                    }
                    response = await self.route_message(node_id, search_msg)
                    
                    if response and 'results' in response:
                        for result in response['results']:
                            result['node_id'] = node_id
                            all_results.append(result)
            
            except Exception as e:
                logger.warning(f"Error buscando en nodo {node_id}: {e}")
        
        # Ordenar por score
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'query': query,
            'total_results': len(all_results),
            'results': all_results[:20]  # Top 20
        }
    
    def _format_search_results(self, results: List, query: str) -> Dict:
        """Formatea resultados de búsqueda local."""
        formatted = []
        for doc_id, score in results:
            doc = self.storage.get_document(doc_id)
            if doc:
                formatted.append({
                    'doc_id': doc_id,
                    'score': score,
                    'snippet': doc.content[:200],
                    'node_id': self.node_id
                })
        
        return {
            'query': query,
            'total_results': len(formatted),
            'results': formatted
        }
    
    async def _notify_leader_index_update(self, terms_added: List[str], 
                                         terms_removed: List[str]):
        """Notifica al líder de actualizaciones del índice."""
        leader_id = self.election.current_leader
        
        if leader_id is None:
            return
        
        update_msg = {
            'type': 'balancer_update',
            'node_id': self.node_id,
            'terms_added': terms_added,
            'terms_removed': terms_removed
        }
        
        if leader_id == self.node_id:
            # Procesar localmente
            self.data_balancer.handle_update_index(
                self.node_id, terms_added, terms_removed
            )
        else:
            await self.route_message(leader_id, update_msg)
    
    def get_status(self) -> Dict:
        """Obtiene estado del nodo."""
        return {
            'node_id': self.node_id,
            'binary_address': self.hypercube.binary_address,
            'is_leader': self.data_balancer.is_leader,
            'current_leader': self.election.current_leader if self.election else None,
            'known_neighbors': list(self.known_neighbors),
            'active_nodes': list(self.active_nodes),
            'storage_stats': self.storage.get_stats(),
            'endpoint': f"{self.host}:{self.port}"
        }
    
    # HTTP API (para modo HTTP real)
    
    def create_http_app(self) -> web.Application:
        """Crea aplicación aiohttp con rutas."""
        app = web.Application()
        
        # Rutas
        app.router.add_post('/doc', self._http_add_document)
        app.router.add_get('/search', self._http_search)
        app.router.add_post('/route', self._http_route)
        app.router.add_get('/status', self._http_status)
        app.router.add_get('/neighbors', self._http_neighbors)
        
        # Data Balancer endpoints (si es líder)
        app.router.add_post('/register_node', self._http_register_node)
        app.router.add_post('/update_index', self._http_update_index)
        app.router.add_get('/locate', self._http_locate)
        app.router.add_post('/heartbeat', self._http_heartbeat)
        
        return app
    
    async def _http_add_document(self, request: web.Request) -> web.Response:
        """POST /doc"""
        try:
            data = await request.json()
            result = await self.add_document(
                data['doc_id'],
                data['content'],
                data.get('metadata')
            )
            return web.json_response(result)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=400)
    
    async def _http_search(self, request: web.Request) -> web.Response:
        """GET /search?q=..."""
        query = request.query.get('q', '')
        result = await self.search(query)
        return web.json_response(result)
    
    async def _http_route(self, request: web.Request) -> web.Response:
        """POST /route"""
        try:
            message = await request.json()
            result = await self.handle_message(message)
            return web.json_response(result or {})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _http_status(self, request: web.Request) -> web.Response:
        """GET /status"""
        return web.json_response(self.get_status())
    
    async def _http_neighbors(self, request: web.Request) -> web.Response:
        """GET /neighbors"""
        return web.json_response({
            'node_id': self.node_id,
            'neighbors': list(self.known_neighbors)
        })
    
    async def _http_register_node(self, request: web.Request) -> web.Response:
        """POST /register_node"""
        try:
            data = await request.json()
            result = self.data_balancer.handle_register_node(
                data['node_id'],
                data['endpoint'],
                data.get('capacity', 100)
            )
            return web.json_response(result)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=400)
    
    async def _http_update_index(self, request: web.Request) -> web.Response:
        """POST /update_index"""
        try:
            data = await request.json()
            result = self.data_balancer.handle_update_index(
                data['node_id'],
                data.get('terms_added', []),
                data.get('terms_removed', [])
            )
            return web.json_response(result)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=400)
    
    async def _http_locate(self, request: web.Request) -> web.Response:
        """GET /locate?q=term"""
        term = request.query.get('q', '')
        result = self.data_balancer.handle_locate(term)
        return web.json_response(result)
    
    async def _http_heartbeat(self, request: web.Request) -> web.Response:
        """POST /heartbeat"""
        try:
            data = await request.json()
            result = self.data_balancer.handle_heartbeat(data['node_id'])
            return web.json_response(result)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=400)
    
    async def start_http_server(self):
        """Inicia servidor HTTP."""
        self.app = self.create_http_app()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Servidor HTTP iniciado en {self.host}:{self.port}")
    
    async def shutdown(self):
        """Cierra el nodo limpiamente."""
        logger.info(f"Apagando nodo {self.node_id}...")
        
        # Guardar índice
        self.storage.save()
        
        # Detener data balancer
        await self.data_balancer.shutdown()
        
        # Cerrar servidor HTTP
        if self.runner:
            await self.runner.cleanup()
        
        # Desregistrar de la red
        await self.network.unregister_node(self.node_id)
        
        logger.info(f"Nodo {self.node_id} apagado")

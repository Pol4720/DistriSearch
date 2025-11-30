"""
Módulo de API HTTP.
Maneja el servidor HTTP y endpoints REST del nodo.
"""
import logging
from typing import Optional
from aiohttp import web

from metrics import export_metrics

logger = logging.getLogger(__name__)


class NodeHTTP:
    """
    Mixin que añade servidor HTTP al nodo.
    Requiere que la clase tenga: node_id, host, port, security,
    add_document, search, get_status, handle_message
    """
    
    def __init__(self):
        """Inicializa servidor HTTP."""
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
    
    def create_http_app(self) -> web.Application:
        """
        Crea aplicación aiohttp con todas las rutas.
        
        Returns:
            Aplicación web configurada
        """
        app = web.Application()
        
        # Rutas del nodo
        app.router.add_post('/doc', self._http_add_document)
        app.router.add_get('/search', self._http_search)
        app.router.add_post('/route', self._http_route)
        app.router.add_get('/status', self._http_status)
        app.router.add_get('/neighbors', self._http_neighbors)
        app.router.add_get('/metrics', self._http_metrics)
        
        # Rutas del Data Balancer (delegadas, verifican si es líder)
        app.router.add_post('/register_node', self._http_register_node)
        app.router.add_post('/update_index', self._http_update_index)
        app.router.add_get('/locate', self._http_locate)
        app.router.add_post('/heartbeat', self._http_heartbeat)
        
        logger.info(f"Nodo {self.node_id}: HTTP app creada con {len(app.router._resources)} rutas")
        
        return app
    
    async def start_http_server(self):
        """
        Inicia servidor HTTP en host:port configurado.
        Soporta TLS si está habilitado en security.
        """
        self.app = self.create_http_app()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Usar SSL si está habilitado
        ssl_context = self.security.get_ssl_context()
        
        site = web.TCPSite(
            self.runner, 
            self.host, 
            self.port, 
            ssl_context=ssl_context
        )
        await site.start()
        
        protocol = "https" if ssl_context else "http"
        logger.info(
            f"Nodo {self.node_id}: servidor HTTP en "
            f"{protocol}://{self.host}:{self.port}"
        )
    
    async def stop_http_server(self):
        """Detiene servidor HTTP limpiamente."""
        if self.runner:
            await self.runner.cleanup()
            logger.info(f"Nodo {self.node_id}: servidor HTTP detenido")
    
    # ══════════════════════════════════════════════════════════
    # Handlers de Rutas del Nodo
    # ══════════════════════════════════════════════════════════
    
    async def _http_add_document(self, request: web.Request) -> web.Response:
        """
        POST /doc
        
        Body: {
            "doc_id": "doc123",
            "content": "texto del documento",
            "metadata": {...}  // opcional
        }
        
        Returns: {
            "status": "ok"|"error",
            "doc_id": "doc123",
            "replicas": [1, 3, 5],
            "terms_indexed": 42
        }
        """
        try:
            data = await request.json()
            doc_id = data.get('doc_id')
            content = data.get('content')
            metadata = data.get('metadata', {})
            
            if not doc_id or not content:
                return web.json_response(
                    {'error': 'doc_id y content son requeridos'}, 
                    status=400
                )
            
            result = await self.add_document(doc_id, content, metadata)
            
            status_code = 200 if result.get('status') == 'ok' else 500
            return web.json_response(result, status=status_code)
        except Exception as e:
            logger.error(f"Error añadiendo documento: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _http_search(self, request: web.Request) -> web.Response:
        """
        GET /search?q={query}&top_k={n}
        
        Returns: {
            "query": "python programming",
            "total_results": 5,
            "results": [
                {
                    "doc_id": "doc1",
                    "score": 3.5,
                    "snippet": "...",
                    "node_id": 3
                },
                ...
            ],
            "nodes_searched": 3,
            "failed_nodes": 0
        }
        """
        try:
            query = request.query.get('q', '')
            top_k = int(request.query.get('top_k', '10'))
            
            if not query:
                return web.json_response(
                    {'error': 'Parámetro q (query) es requerido'}, 
                    status=400
                )
            
            result = await self.search(query, top_k)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _http_route(self, request: web.Request) -> web.Response:
        """
        POST /route
        
        Body: {cualquier mensaje para handle_message}
        
        Returns: {respuesta del handler}
        """
        try:
            message = await request.json()
            response = await self.handle_message(message)
            return web.json_response(response or {})
        except Exception as e:
            logger.error(f"Error ruteando mensaje: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _http_status(self, request: web.Request) -> web.Response:
        """
        GET /status
        
        Returns: {
            "node_id": 5,
            "binary_address": "00000000000000000101",
            "raft_state": "LEADER",
            "raft_term": 3,
            "current_leader": 5,
            "known_neighbors": [1, 4, 7, ...],
            "active_nodes": [0, 1, 2, ...],
            "storage_stats": {...},
            "cache_stats": {...},
            "shard_stats": {...}
        }
        """
        return web.json_response(self.get_status())
    
    async def _http_neighbors(self, request: web.Request) -> web.Response:
        """
        GET /neighbors
        
        Returns: {
            "node_id": 5,
            "neighbors": [1, 4, 7, ...]
        }
        """
        return web.json_response({
            'node_id': self.node_id,
            'neighbors': list(self.known_neighbors)
        })
    
    async def _http_metrics(self, request: web.Request) -> web.Response:
        """
        GET /metrics
        
        Returns: Métricas en formato Prometheus
        """
        metrics_bytes = export_metrics()
        return web.Response(
            body=metrics_bytes,
            content_type='text/plain; charset=utf-8'
        )
    
    # ══════════════════════════════════════════════════════════
    # Handlers de Data Balancer (Stubs - por implementar)
    # ══════════════════════════════════════════════════════════
    
    async def _http_register_node(self, request: web.Request) -> web.Response:
        """
        POST /register_node
        
        Registra un nuevo nodo en el Data Balancer.
        TODO: Implementar cuando se integre Data Balancer HTTP.
        """
        return web.json_response(
            {'error': 'not_implemented'}, 
            status=501
        )
    
    async def _http_update_index(self, request: web.Request) -> web.Response:
        """
        POST /update_index
        
        Actualiza el índice global en el Data Balancer.
        TODO: Implementar cuando se integre Data Balancer HTTP.
        """
        return web.json_response(
            {'error': 'not_implemented'}, 
            status=501
        )
    
    async def _http_locate(self, request: web.Request) -> web.Response:
        """
        GET /locate?term={term}
        
        Localiza nodos que contienen un término.
        TODO: Implementar cuando se integre Data Balancer HTTP.
        """
        return web.json_response(
            {'error': 'not_implemented'}, 
            status=501
        )
    
    async def _http_heartbeat(self, request: web.Request) -> web.Response:
        """
        POST /heartbeat
        
        Recibe heartbeat de un nodo.
        TODO: Implementar cuando se integre Data Balancer HTTP.
        """
        return web.json_response(
            {'error': 'not_implemented'}, 
            status=501
        )

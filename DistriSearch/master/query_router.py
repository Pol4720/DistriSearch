"""
DistriSearch Master - Query Router

Enruta búsquedas a los Slaves más relevantes
basándose en afinidad semántica.
"""
import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from .embedding_service import EmbeddingService, get_embedding_service
from .location_index import SemanticLocationIndex
from .load_balancer import LoadBalancer
from ..core.models import QueryResult

logger = logging.getLogger(__name__)


@dataclass
class QueryRequest:
    """Solicitud de búsqueda"""
    query_id: str
    query_text: str
    query_embedding: Optional[np.ndarray] = None
    limit: int = 10
    search_type: str = "semantic"  # semantic, filename, hybrid
    node_filter: Optional[List[str]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AggregatedResult:
    """Resultados agregados de múltiples nodos"""
    query_id: str
    results: List[QueryResult]
    nodes_queried: List[str]
    nodes_responded: List[str]
    total_time_ms: float
    errors: Dict[str, str] = field(default_factory=dict)


class QueryRouter:
    """
    Router de queries para búsquedas distribuidas.
    
    Funcionalidades:
    - Genera embedding de la query
    - Identifica Slaves relevantes por afinidad semántica
    - Envía queries en paralelo
    - Agrega y rankea resultados
    """
    
    def __init__(
        self,
        location_index: SemanticLocationIndex,
        load_balancer: LoadBalancer,
        embedding_service: Optional[EmbeddingService] = None,
        max_nodes_per_query: int = 3,
        timeout: float = 10.0
    ):
        """
        Args:
            location_index: Índice de ubicación semántica
            load_balancer: Balanceador de carga
            embedding_service: Servicio de embeddings
            max_nodes_per_query: Máximo de nodos a consultar por query
            timeout: Timeout para requests HTTP
        """
        self.location_index = location_index
        self.load_balancer = load_balancer
        self.embedding_service = embedding_service or get_embedding_service()
        self.max_nodes_per_query = max_nodes_per_query
        self.timeout = timeout
        
        # Endpoints de nodos: node_id -> base_url
        self._node_endpoints: Dict[str, str] = {}
        
        # Métricas
        self._queries_processed = 0
        self._total_latency_ms = 0.0
    
    def register_node(self, node_id: str, base_url: str) -> None:
        """Registra endpoint de un nodo"""
        self._node_endpoints[node_id] = base_url.rstrip('/')
    
    def unregister_node(self, node_id: str) -> None:
        """Elimina nodo del router"""
        self._node_endpoints.pop(node_id, None)
    
    async def route_query(self, request: QueryRequest) -> AggregatedResult:
        """
        Enruta una query a los nodos apropiados y agrega resultados.
        
        Args:
            request: Solicitud de búsqueda
            
        Returns:
            Resultados agregados de todos los nodos
        """
        start_time = datetime.utcnow()
        
        # Generar embedding si no existe
        if request.query_embedding is None:
            request.query_embedding = self.embedding_service.encode_query(
                request.query_text
            )
        
        # Seleccionar nodos a consultar
        target_nodes = self._select_nodes(request)
        
        if not target_nodes:
            logger.warning(f"No hay nodos disponibles para query {request.query_id}")
            return AggregatedResult(
                query_id=request.query_id,
                results=[],
                nodes_queried=[],
                nodes_responded=[],
                total_time_ms=0.0
            )
        
        # Notificar al balanceador
        for node_id in target_nodes:
            self.load_balancer.increment_queries(node_id)
        
        try:
            # Enviar queries en paralelo
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                tasks = [
                    self._query_node(client, node_id, request)
                    for node_id in target_nodes
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Procesar respuestas
            all_results: List[QueryResult] = []
            nodes_responded: List[str] = []
            errors: Dict[str, str] = {}
            
            for node_id, response in zip(target_nodes, responses):
                if isinstance(response, Exception):
                    errors[node_id] = str(response)
                    logger.error(f"Error consultando {node_id}: {response}")
                elif response:
                    all_results.extend(response)
                    nodes_responded.append(node_id)
            
            # Agregar y rankear resultados
            final_results = self._aggregate_results(
                all_results, 
                request.query_embedding,
                request.limit
            )
            
            # Calcular tiempo total
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Actualizar métricas
            self._queries_processed += 1
            self._total_latency_ms += elapsed
            
            return AggregatedResult(
                query_id=request.query_id,
                results=final_results,
                nodes_queried=target_nodes,
                nodes_responded=nodes_responded,
                total_time_ms=elapsed,
                errors=errors
            )
            
        finally:
            # Liberar contador en balanceador
            for node_id in target_nodes:
                self.load_balancer.decrement_queries(node_id)
    
    def _select_nodes(self, request: QueryRequest) -> List[str]:
        """Selecciona nodos para la query"""
        # Si hay filtro explícito, usarlo
        if request.node_filter:
            return [
                node_id for node_id in request.node_filter
                if node_id in self._node_endpoints
            ]
        
        # Obtener scores semánticos del índice
        semantic_scores = None
        if request.query_embedding is not None:
            semantic_scores = self.location_index.find_nodes_for_query(
                request.query_embedding,
                top_k=self.max_nodes_per_query * 2  # Obtener más para filtrar
            )
        
        # Usar balanceador para selección final
        return self.load_balancer.select_nodes_for_query(
            semantic_scores=semantic_scores,
            num_nodes=self.max_nodes_per_query
        )
    
    async def _query_node(
        self, 
        client: httpx.AsyncClient,
        node_id: str,
        request: QueryRequest
    ) -> List[QueryResult]:
        """Envía query a un nodo específico"""
        base_url = self._node_endpoints.get(node_id)
        if not base_url:
            return []
        
        try:
            # Construir request
            url = f"{base_url}/api/search"
            payload = {
                "query": request.query_text,
                "limit": request.limit * 2,  # Pedir más para agregación
                "search_type": request.search_type
            }
            
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Convertir a QueryResult
            results = []
            for item in data.get("results", []):
                results.append(QueryResult(
                    file_id=item.get("file_id", ""),
                    filename=item.get("filename", ""),
                    score=item.get("score", 0.0),
                    node_id=node_id,
                    snippet=item.get("snippet"),
                    metadata=item.get("metadata", {})
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error consultando nodo {node_id}: {e}")
            raise
    
    def _aggregate_results(
        self,
        results: List[QueryResult],
        query_embedding: np.ndarray,
        limit: int
    ) -> List[QueryResult]:
        """
        Agrega resultados de múltiples nodos.
        
        Re-rankea usando similitud con el embedding de la query.
        """
        if not results:
            return []
        
        # Eliminar duplicados (mismo file_id)
        seen = set()
        unique_results = []
        for result in results:
            if result.file_id not in seen:
                seen.add(result.file_id)
                unique_results.append(result)
        
        # Ordenar por score y limitar
        unique_results.sort(key=lambda r: r.score, reverse=True)
        
        return unique_results[:limit]
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        search_type: str = "semantic"
    ) -> AggregatedResult:
        """
        Método de conveniencia para búsqueda simple.
        
        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados
            search_type: Tipo de búsqueda
            
        Returns:
            Resultados agregados
        """
        import uuid
        
        request = QueryRequest(
            query_id=str(uuid.uuid4()),
            query_text=query,
            limit=limit,
            search_type=search_type
        )
        
        return await self.route_query(request)
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del router"""
        avg_latency = (
            self._total_latency_ms / self._queries_processed 
            if self._queries_processed > 0 else 0
        )
        
        return {
            "registered_nodes": len(self._node_endpoints),
            "max_nodes_per_query": self.max_nodes_per_query,
            "queries_processed": self._queries_processed,
            "average_latency_ms": avg_latency,
            "timeout": self.timeout
        }

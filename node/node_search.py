"""
Módulo de búsqueda distribuida.
Maneja búsquedas en múltiples nodos con tolerancia a fallos.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


class NodeSearch:
    """
    Mixin que añade capacidades de búsqueda distribuida al nodo.
    Requiere que la clase tenga: node_id, storage, cache, route_message,
    consensus, data_balancer
    """
    
    async def search(self, query: str, top_k: int = 10) -> Dict:
        """
        Búsqueda distribuida CON tolerancia a fallos de réplicas.
        
        Algoritmo:
        1. Tokenizar consulta
        2. Localizar nodos para cada término (con cache)
        3. Buscar en paralelo en nodos candidatos
        4. Si algún nodo falla, intentar réplicas
        5. Agregar y ordenar resultados por score
        6. Retornar top-k
        
        Args:
            query: Consulta textual
            top_k: Número máximo de resultados
            
        Returns:
            Dict con query, total_results, results, estadísticas
        """
        logger.info(f"Nodo {self.node_id}: Búsqueda distribuida: '{query}'")
        
        # 1. Tokenizar consulta
        query_terms = self.storage.tokenize(query)
        
        if not query_terms:
            return {
                "query": query,
                "total_results": 0,
                "results": []
            }
        
        # 2. Localizar nodos para cada término (con cache)
        candidate_nodes: Set[int] = set()
        
        for term in query_terms:
            # Consultar cache primero
            cached = await self.cache.get(f"term_location:{term}")
            
            if cached:
                nodes = cached
                logger.debug(f"Cache HIT para término '{term}': {nodes}")
            else:
                # Cache MISS: consultar líder
                nodes = await self._locate_term_nodes(term)
                
                # Guardar en cache (TTL implícito en cache)
                await self.cache.put(f"term_location:{term}", nodes)
            
            candidate_nodes.update(nodes)
        
        logger.debug(f"Nodos candidatos: {candidate_nodes}")
        
        # 3. Buscar en nodos candidatos (incluyendo local)
        search_tasks = []
        
        for node_id in candidate_nodes:
            if node_id == self.node_id:
                # Búsqueda local
                task = self._search_local(query)
            else:
                # Búsqueda remota
                task = self._search_node(node_id, query)
            
            search_tasks.append((node_id, task))
        
        # 4. Agregar resultados (con timeouts y fallback a réplicas)
        all_results = []
        failed_nodes = set()
        
        for node_id, task in search_tasks:
            try:
                results = await asyncio.wait_for(task, timeout=5.0)
                if results:
                    all_results.extend(results)
                    logger.debug(f"Nodo {node_id}: {len(results)} resultados")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout buscando en nodo {node_id}")
                failed_nodes.add(node_id)
            except Exception as e:
                logger.error(f"Error buscando en nodo {node_id}: {e}")
                failed_nodes.add(node_id)
        
        # 5. FALLBACK: Si algún nodo falló, intentar sus réplicas
        if failed_nodes:
            logger.info(
                f"Intentando réplicas para nodos fallidos: {failed_nodes}"
            )
            all_results.extend(
                await self._search_replicas(
                    query, query_terms, failed_nodes, candidate_nodes
                )
            )
        
        # 6. Ordenar y limitar resultados
        final_results = self._aggregate_results(all_results, top_k)
        
        return {
            "query": query,
            "total_results": len(final_results),
            "results": final_results,
            "nodes_searched": len(candidate_nodes),
            "failed_nodes": len(failed_nodes)
        }
    
    async def _search_local(self, query: str) -> List[Dict]:
        """
        Búsqueda local en este nodo.
        
        Args:
            query: Consulta textual
            
        Returns:
            Lista de resultados con doc_id, score, snippet, node_id
        """
        results = self.storage.search(query)
        
        formatted = []
        for doc_id, score in results:
            doc = self.storage.get_document(doc_id)
            if doc:
                formatted.append({
                    'doc_id': doc_id,
                    'score': score,
                    'snippet': doc.content[:100],
                    'node_id': self.node_id
                })
        
        return formatted
    
    async def _search_node(self, node_id: int, query: str) -> List[Dict]:
        """
        Búsqueda remota en otro nodo.
        
        Args:
            node_id: ID del nodo destino
            query: Consulta textual
            
        Returns:
            Lista de resultados del nodo remoto
        """
        try:
            response = await self.route_message(
                node_id,
                {
                    "type": "search_local",
                    "query": query
                }
            )
            
            return response.get("results", []) if response else []
        except Exception as e:
            logger.error(f"Error buscando en nodo {node_id}: {e}")
            return []
    
    async def _search_replicas(
        self,
        query: str,
        query_terms: List[str],
        failed_nodes: Set[int],
        candidate_nodes: Set[int]
    ) -> List[Dict]:
        """
        Busca en réplicas alternativas de nodos que fallaron.
        
        Args:
            query: Consulta textual
            query_terms: Términos tokenizados
            failed_nodes: Conjunto de nodos que fallaron
            candidate_nodes: Conjunto de nodos ya consultados
            
        Returns:
            Lista de resultados de réplicas
        """
        replica_tasks = []
        
        for term in query_terms:
            nodes_for_term = await self._locate_term_nodes(term)
            
            # Filtrar nodos que no fallaron y no fueron consultados
            available_replicas = [
                n for n in nodes_for_term 
                if n not in failed_nodes and n not in candidate_nodes
            ]
            
            for replica_id in available_replicas:
                if replica_id != self.node_id:
                    task = self._search_node(replica_id, query)
                    replica_tasks.append(task)
        
        # Ejecutar búsquedas de réplicas
        all_results = []
        for task in replica_tasks:
            try:
                results = await asyncio.wait_for(task, timeout=3.0)
                if results:
                    all_results.extend(results)
            except:
                pass  # Silenciar errores de réplicas
        
        return all_results
    
    def _aggregate_results(
        self, 
        all_results: List[Dict], 
        top_k: int
    ) -> List[Dict]:
        """
        Agrega y ordena resultados de múltiples nodos.
        
        Args:
            all_results: Lista de todos los resultados
            top_k: Número máximo de resultados a retornar
            
        Returns:
            Lista ordenada de top-k resultados
        """
        # Agrupar por doc_id y sumar scores
        doc_scores: Dict[str, float] = defaultdict(float)
        doc_metadata: Dict[str, Dict] = {}
        
        for result in all_results:
            doc_id = result['doc_id']
            doc_scores[doc_id] += result['score']
            
            if doc_id not in doc_metadata:
                doc_metadata[doc_id] = result
        
        # Ordenar por score
        sorted_docs = sorted(
            doc_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Top-k resultados
        final_results = []
        for doc_id, total_score in sorted_docs[:top_k]:
            result = doc_metadata[doc_id].copy()
            result['score'] = total_score
            final_results.append(result)
        
        return final_results
    
    async def _locate_term_nodes(self, term: str) -> Set[int]:
        """
        Localiza nodos que contienen un término usando sharding.
        
        Args:
            term: Término a buscar
            
        Returns:
            Conjunto de IDs de nodos que contienen el término
        """
        # Verificar si hay líder
        if self.consensus.current_leader is None:
            logger.warning("No hay líder, búsqueda puede fallar")
            # Fallback: buscar solo localmente
            if term in self.storage.index:
                return {self.node_id}
            return set()
        
        # Determinar shard coordinator del término
        try:
            shard_coord = self.data_balancer.shard_manager.get_shard_coordinator(
                term
            )
        except ValueError as e:
            logger.error(f"Error obteniendo shard coordinator: {e}")
            # Fallback: buscar localmente
            if term in self.storage.index:
                return {self.node_id}
            return set()
        
        if shard_coord == self.node_id:
            # Consulta local al shard
            return self.data_balancer.shard_manager.get_nodes_for_term(term)
        else:
            # Consultar remotamente
            try:
                message = {
                    'type': 'locate_term',
                    'term': term
                }
                response = await self.route_message(shard_coord, message)
                
                if response and 'nodes' in response:
                    return set(response['nodes'])
                else:
                    logger.warning(
                        f"Respuesta inválida al localizar término '{term}': "
                        f"{response}"
                    )
                    return set()
            except Exception as e:
                logger.error(f"Error localizando término '{term}': {e}")
                return set()
    
    def handle_search_local(self, message: Dict) -> Dict:
        """
        Maneja mensaje de búsqueda local.
        
        Args:
            message: Mensaje con query
            
        Returns:
            Dict con query, total_results, results
        """
        query = message.get('query', '')
        results = self.storage.search(query)
        
        formatted = []
        for doc_id, score in results:
            doc = self.storage.get_document(doc_id)
            if doc:
                snippet = (
                    doc.content[:100] + "..." 
                    if len(doc.content) > 100 
                    else doc.content
                )
                formatted.append({
                    'doc_id': doc_id,
                    'score': score,
                    'snippet': snippet,
                    'node_id': self.node_id
                })
        
        return {
            'query': query,
            'total_results': len(formatted),
            'results': formatted
        }

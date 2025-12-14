# -*- coding: utf-8 -*-
"""
Search Engine - Coordinates distributed search operations.

Handles:
- Query processing
- Distributed search across cluster nodes
- Result aggregation
- Caching
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .query_processor import QueryProcessor, ProcessedQuery, QueryType
from .result_aggregator import ResultAggregator, SearchResult, AggregatedResults, RankingStrategy

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configuration for search operations."""
    # Timeouts
    search_timeout_sec: float = 10.0
    node_timeout_sec: float = 5.0
    
    # Results
    default_page_size: int = 20
    max_page_size: int = 100
    max_total_results: int = 1000
    
    # Behavior
    min_nodes_required: int = 1
    allow_partial_results: bool = True
    enable_caching: bool = True
    cache_ttl_sec: float = 300.0
    
    # Ranking
    default_ranking: RankingStrategy = RankingStrategy.HYBRID


class SearchEngine:
    """
    Distributed search engine for document retrieval.
    
    Coordinates search across cluster nodes and aggregates results.
    """
    
    def __init__(
        self,
        config: Optional[SearchConfig] = None,
        query_node_func: Optional[Callable[[str, ProcessedQuery, int], Awaitable[List[SearchResult]]]] = None,
        get_target_nodes_func: Optional[Callable[[ProcessedQuery], Awaitable[List[str]]]] = None,
        vectorizer: Optional[Any] = None
    ):
        """
        Initialize search engine.
        
        Args:
            config: Search configuration
            query_node_func: Function to query a node
                            Signature: (node_id, query, limit) -> results
            get_target_nodes_func: Function to get nodes to query
                                   Signature: (query) -> node_ids
            vectorizer: Document vectorizer for query processing
        """
        self.config = config or SearchConfig()
        self._query_node = query_node_func
        self._get_targets = get_target_nodes_func
        
        # Components
        self.query_processor = QueryProcessor(vectorizer=vectorizer)
        self.aggregator = ResultAggregator(
            default_strategy=self.config.default_ranking
        )
        
        # Cache
        self._cache: Dict[str, tuple] = {}  # query_hash -> (results, timestamp)
        
        # Statistics
        self._total_searches = 0
        self._cache_hits = 0
        self._failed_searches = 0
    
    def set_query_function(
        self,
        func: Callable[[str, ProcessedQuery, int], Awaitable[List[SearchResult]]]
    ) -> None:
        """Set the node query function."""
        self._query_node = func
    
    def set_target_function(
        self,
        func: Callable[[ProcessedQuery], Awaitable[List[str]]]
    ) -> None:
        """Set the target nodes function."""
        self._get_targets = func
    
    def set_vectorizer(self, vectorizer: Any) -> None:
        """Set the query vectorizer."""
        self.query_processor.set_vectorizer(vectorizer)
    
    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: Optional[int] = None,
        ranking: Optional[RankingStrategy] = None,
        filters: Optional[Dict[str, Any]] = None,
        target_nodes: Optional[List[str]] = None
    ) -> AggregatedResults:
        """
        Execute a distributed search.
        
        Args:
            query: Search query string
            page: Page number (1-indexed)
            page_size: Results per page
            ranking: Ranking strategy
            filters: Additional filters
            target_nodes: Specific nodes to query (auto-select if None)
            
        Returns:
            Aggregated search results
        """
        self._total_searches += 1
        start_time = datetime.utcnow()
        
        page_size = min(
            page_size or self.config.default_page_size,
            self.config.max_page_size
        )
        ranking = ranking or self.config.default_ranking
        
        # Check cache
        cache_key = self._get_cache_key(query, filters)
        if self.config.enable_caching:
            cached = self._get_cached(cache_key)
            if cached:
                self._cache_hits += 1
                return self._paginate_cached(cached, page, page_size, ranking)
        
        try:
            # Process query
            processed = self.query_processor.process(query)
            
            # Apply additional filters
            if filters:
                processed.filters.update(filters)
            
            # Get target nodes
            if target_nodes is None:
                target_nodes = await self._determine_target_nodes(processed)
            
            if not target_nodes:
                logger.warning("No target nodes for search")
                return self._empty_results(query, start_time)
            
            # Query nodes in parallel
            node_results = await self._query_nodes(processed, target_nodes)
            
            # Check minimum nodes requirement
            if len(node_results) < self.config.min_nodes_required:
                if not self.config.allow_partial_results:
                    raise RuntimeError(
                        f"Insufficient nodes responded: {len(node_results)}/{self.config.min_nodes_required}"
                    )
            
            # Aggregate results
            results = self.aggregator.aggregate(
                query=query,
                node_results=node_results,
                nodes_queried=target_nodes,
                strategy=ranking,
                page=page,
                page_size=page_size,
                max_results=self.config.max_total_results
            )
            
            # Cache results
            if self.config.enable_caching and results.total_results > 0:
                self._set_cached(cache_key, results)
            
            return results
            
        except Exception as e:
            self._failed_searches += 1
            logger.error(f"Search failed: {e}")
            raise
    
    async def _determine_target_nodes(
        self,
        processed: ProcessedQuery
    ) -> List[str]:
        """Determine which nodes to query."""
        if self._get_targets:
            return await self._get_targets(processed)
        
        # Default: would return all known nodes
        logger.warning("No target function set, returning empty")
        return []
    
    async def _query_nodes(
        self,
        query: ProcessedQuery,
        nodes: List[str]
    ) -> Dict[str, List[SearchResult]]:
        """
        Query multiple nodes in parallel.
        
        Args:
            query: Processed query
            nodes: Nodes to query
            
        Returns:
            Results per node
        """
        if not self._query_node:
            logger.warning("No query function set")
            return {}
        
        # Calculate per-node limit (request more than needed for better ranking)
        per_node_limit = min(
            self.config.max_total_results // max(len(nodes), 1) * 2,
            200
        )
        
        # Create tasks
        tasks = {
            node: asyncio.create_task(
                self._query_single_node(node, query, per_node_limit)
            )
            for node in nodes
        }
        
        # Wait with timeout
        results = {}
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=self.config.search_timeout_sec
        )
        
        # Cancel pending
        for task in pending:
            task.cancel()
        
        # Collect results
        for node, task in tasks.items():
            if task in done:
                try:
                    result = task.result()
                    if result:
                        results[node] = result
                except Exception as e:
                    logger.warning(f"Query to {node} failed: {e}")
        
        return results
    
    async def _query_single_node(
        self,
        node_id: str,
        query: ProcessedQuery,
        limit: int
    ) -> List[SearchResult]:
        """Query a single node with timeout."""
        try:
            return await asyncio.wait_for(
                self._query_node(node_id, query, limit),
                timeout=self.config.node_timeout_sec
            )
        except asyncio.TimeoutError:
            logger.warning(f"Query to {node_id} timed out")
            return []
        except Exception as e:
            logger.warning(f"Query to {node_id} error: {e}")
            return []
    
    def _get_cache_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for query."""
        filter_str = str(sorted(filters.items())) if filters else ""
        return f"{query}|{filter_str}"
    
    def _get_cached(self, key: str) -> Optional[AggregatedResults]:
        """Get cached results if valid."""
        if key not in self._cache:
            return None
        
        results, timestamp = self._cache[key]
        age = (datetime.utcnow() - timestamp).total_seconds()
        
        if age > self.config.cache_ttl_sec:
            del self._cache[key]
            return None
        
        return results
    
    def _set_cached(self, key: str, results: AggregatedResults) -> None:
        """Cache search results."""
        self._cache[key] = (results, datetime.utcnow())
        
        # Limit cache size
        if len(self._cache) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k][1]
            )
            for old_key in sorted_keys[:100]:
                del self._cache[old_key]
    
    def _paginate_cached(
        self,
        cached: AggregatedResults,
        page: int,
        page_size: int,
        ranking: RankingStrategy
    ) -> AggregatedResults:
        """Return paginated view of cached results."""
        # Re-aggregate with requested pagination
        return self.aggregator.aggregate(
            query=cached.query,
            node_results={
                cached.nodes_responded[0] if cached.nodes_responded else "cached": cached.results
            },
            nodes_queried=cached.nodes_queried,
            strategy=ranking,
            page=page,
            page_size=page_size
        )
    
    def _empty_results(
        self,
        query: str,
        start_time: datetime
    ) -> AggregatedResults:
        """Return empty results."""
        return AggregatedResults(
            query=query,
            results=[],
            total_results=0,
            nodes_queried=[],
            nodes_responded=[],
            search_started=start_time,
            search_completed=datetime.utcnow()
        )
    
    async def search_by_id(
        self,
        document_id: str,
        include_similar: bool = False,
        similar_limit: int = 10
    ) -> Optional[SearchResult]:
        """
        Search for a specific document by ID.
        
        Args:
            document_id: Document identifier
            include_similar: Whether to include similar documents
            similar_limit: Number of similar documents
            
        Returns:
            Search result or None
        """
        # This would be implemented by querying nodes for the specific document
        # Simplified for now
        pass
    
    async def get_suggestions(
        self,
        partial_query: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get search suggestions for partial query.
        
        Args:
            partial_query: Partial query string
            limit: Maximum suggestions
            
        Returns:
            List of suggested queries
        """
        # This would be implemented with query logging and analysis
        # Simplified for now
        return []
    
    def clear_cache(self) -> int:
        """Clear search cache."""
        count = len(self._cache)
        self._cache.clear()
        return count
    
    async def vectorize_document(self, content: str, title: str = "") -> Dict[str, Any]:
        """
        Vectorize a document for indexing.
        
        Args:
            content: Document content
            title: Document title (optional)
            
        Returns:
            Dictionary with vector representations matching DocumentVectors schema
        """
        import hashlib
        import re
        
        # Simple TF-IDF-like representation (word frequencies as float list)
        words = re.findall(r'\b\w+\b', content.lower())
        word_freq = {}
        for word in words:
            if len(word) > 2:  # Skip very short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Top words as TF-IDF approximation - convert to float list
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        tfidf_vector = [float(c) / len(words) for _, c in sorted_words]
        
        # MinHash signature (simple hash-based approach) - list of ints
        content_hash = hashlib.md5(content.encode()).hexdigest()
        minhash_sig = [int(content_hash[i:i+2], 16) for i in range(0, min(32, len(content_hash)), 2)]
        
        # Simple keyword extraction - list of strings
        textrank_keywords = [w for w, _ in sorted_words[:10]]
        
        # Pseudo-LDA topics - list of floats (topic probabilities)
        topic_words = {
            "technology": ["software", "computer", "system", "data", "code", "algorithm"],
            "business": ["company", "market", "business", "revenue", "strategy", "customer"],
            "science": ["research", "study", "experiment", "theory", "hypothesis", "analysis"],
        }
        lda_topics = []
        for topic, keywords in topic_words.items():
            score = sum(1 for kw in keywords if kw in word_freq)
            lda_topics.append(float(score) / max(len(keywords), 1))
        
        # Normalize LDA to sum to 1
        total = sum(lda_topics) or 1.0
        lda_topics = [t / total for t in lda_topics]
        
        return {
            "tfidf": tfidf_vector,
            "minhash": minhash_sig,
            "textrank": textrank_keywords,
            "lda": lda_topics
        }
    
    async def vectorize_query(self, query: str) -> Dict[str, Any]:
        """
        Vectorize a search query.
        
        Args:
            query: Search query string
            
        Returns:
            Dictionary with query vector representation
        """
        # Reuse document vectorization for query
        return await self.vectorize_document(query)
    
    async def distributed_search(
        self,
        query: str,
        query_vectors: Dict[str, Any],
        search_type: str = "hybrid",
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        target_partitions: Optional[List[str]] = None,
        timeout_ms: int = 5000,
        cluster_manager: Any = None,
        document_repository: Any = None
    ) -> Dict[str, Any]:
        """
        Execute distributed search across cluster.
        
        Args:
            query: Search query string
            query_vectors: Vectorized query
            search_type: Type of search (keyword, semantic, hybrid)
            top_k: Number of results to return
            filters: Optional filters
            target_partitions: Partitions to search
            timeout_ms: Timeout in milliseconds
            cluster_manager: Cluster manager for node communication
            document_repository: Document repository for local search
            
        Returns:
            Search results dictionary
        """
        import re
        
        results = []
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        
        if document_repository:
            # Search locally using repository
            all_docs = await document_repository.find_many({}, limit=1000)
            
            for doc in all_docs:
                doc_dict = doc if isinstance(doc, dict) else doc.dict()
                content = doc_dict.get("content", "").lower()
                title = doc_dict.get("title", "").lower()
                
                # Calculate match score based on query terms
                doc_terms = set(re.findall(r'\b\w+\b', content + " " + title))
                matched_terms = query_terms & doc_terms
                
                if matched_terms:
                    # Simple scoring: percentage of query terms matched
                    score = len(matched_terms) / len(query_terms) if query_terms else 0
                    
                    # Get document ID (could be _id or id depending on source)
                    doc_id = doc_dict.get("id") or doc_dict.get("_id", "")
                    if hasattr(doc_id, '__str__'):
                        doc_id = str(doc_id)
                    
                    results.append({
                        "document_id": doc_id,
                        "title": doc_dict.get("title", "Untitled"),
                        "content": doc_dict.get("content", ""),
                        "score": score,
                        "node_id": doc_dict.get("node_id", ""),
                        "metadata": doc_dict.get("metadata", {}),
                        "matched_terms": list(matched_terms),
                        "vectors": doc_dict.get("vectors", {})
                    })
            
            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
        
        return {
            "results": results,
            "query": query,
            "search_type": search_type,
            "total_results": len(results),
            "partitions_searched": target_partitions or [],
            "timeout_ms": timeout_ms
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get search engine statistics."""
        return {
            "total_searches": self._total_searches,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / self._total_searches if self._total_searches > 0 else 0,
            "failed_searches": self._failed_searches,
            "cache_size": len(self._cache),
            "config": {
                "search_timeout_sec": self.config.search_timeout_sec,
                "default_page_size": self.config.default_page_size,
                "enable_caching": self.config.enable_caching
            }
        }

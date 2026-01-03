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
import math
import os
from typing import List, Dict, Any, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import redis

from .query_processor import QueryProcessor, ProcessedQuery, QueryType
from .result_aggregator import ResultAggregator, SearchResult, AggregatedResults, RankingStrategy

logger = logging.getLogger(__name__)

# Redis connection for persistent counters
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
        try:
            _redis_client = redis.from_url(redis_url)
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
            return None
    return _redis_client


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
        
        # Increment search counter (local)
        self._total_searches += 1
        
        # Increment in Redis for persistence across workers
        try:
            r = _get_redis()
            if r:
                r.incr("distrisearch:total_searches")
        except Exception as e:
            logger.warning(f"Failed to increment Redis counter: {e}")
        
        results = []
        query_terms = [w for w in re.findall(r'\b\w+\b', query.lower()) if len(w) > 2]
        query_term_set = set(query_terms)
        
        if document_repository:
            # Search locally using repository
            all_docs = await document_repository.find_many({}, limit=1000)
            
            # Build corpus statistics for BM25
            doc_count = len(all_docs)
            avg_doc_length = 0
            term_doc_freq = {}  # How many docs contain each term
            
            # First pass: collect statistics
            doc_data_list = []
            for doc in all_docs:
                doc_dict = doc if isinstance(doc, dict) else doc.dict()
                content = doc_dict.get("content", "").lower()
                title = doc_dict.get("title", "").lower()
                full_text = title + " " + content
                
                doc_terms = re.findall(r'\b\w+\b', full_text)
                doc_terms = [w for w in doc_terms if len(w) > 2]
                avg_doc_length += len(doc_terms)
                
                unique_terms = set(doc_terms)
                for term in unique_terms:
                    term_doc_freq[term] = term_doc_freq.get(term, 0) + 1
                
                doc_data_list.append({
                    "doc_dict": doc_dict,
                    "doc_terms": doc_terms,
                    "term_freq": {},
                    "doc_length": len(doc_terms)
                })
            
            avg_doc_length = avg_doc_length / doc_count if doc_count > 0 else 1
            
            # Calculate term frequencies for each doc
            for doc_data in doc_data_list:
                for term in doc_data["doc_terms"]:
                    doc_data["term_freq"][term] = doc_data["term_freq"].get(term, 0) + 1
            
            # Second pass: calculate BM25 + vector similarity scores
            # BM25 parameters
            k1 = 1.5  # Term frequency saturation
            b = 0.75  # Length normalization
            
            # Normalize query for substring matching
            query_lower = query.lower().strip()
            
            for doc_data in doc_data_list:
                doc_dict = doc_data["doc_dict"]
                doc_terms_set = set(doc_data["doc_terms"])
                matched_terms = query_term_set & doc_terms_set
                
                # Check for substring match in title/filename
                title_lower = doc_dict.get("title", "").lower()
                filename_lower = doc_dict.get("filename", doc_dict.get("title", "")).lower()
                
                # Check if query is a substring of the filename/title
                is_substring_match = (
                    query_lower in title_lower or 
                    query_lower in filename_lower
                )
                
                # Skip if no term matches AND no substring match
                if not matched_terms and not is_substring_match:
                    continue
                
                # Calculate BM25 score
                bm25_score = 0.0
                for term in query_terms:
                    if term not in doc_data["term_freq"]:
                        continue
                    
                    tf = doc_data["term_freq"][term]
                    df = term_doc_freq.get(term, 1)
                    doc_len = doc_data["doc_length"]
                    
                    # IDF component (with smoothing)
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)
                    
                    # TF component with saturation and length normalization
                    tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_length))
                    
                    bm25_score += idf * tf_component
                
                # Normalize BM25 score (typical range 0-15 for good matches)
                bm25_normalized = min(bm25_score / 10.0, 1.0)
                
                # Calculate TF-IDF vector similarity if vectors exist
                vector_similarity = 0.0
                doc_vectors = doc_dict.get("vectors", {})
                if doc_vectors and doc_vectors.get("tfidf"):
                    doc_tfidf = doc_vectors.get("tfidf", [])
                    # Create query TF-IDF vector based on term frequencies
                    query_tf = {}
                    for term in query_terms:
                        query_tf[term] = query_tf.get(term, 0) + 1
                    
                    # Simple cosine similarity approximation using matched terms
                    if doc_tfidf:
                        # Use overlap coefficient as proxy for vector similarity
                        match_ratio = len(matched_terms) / max(len(query_term_set), 1)
                        vector_similarity = match_ratio * 0.5
                        
                        # Boost if MinHash signatures suggest similarity
                        if doc_vectors.get("minhash"):
                            vector_similarity += 0.1
                
                # Calculate MinHash Jaccard similarity estimate
                minhash_similarity = 0.0
                if doc_vectors and doc_vectors.get("minhash"):
                    # Jaccard estimate from keyword overlap
                    all_terms = query_term_set | doc_terms_set
                    if all_terms:
                        minhash_similarity = len(matched_terms) / len(all_terms)
                
                # Hybrid score with configurable weights
                # Weights: BM25 (60%), TF-IDF vector (25%), MinHash (15%)
                hybrid_score = (
                    0.60 * bm25_normalized +
                    0.25 * vector_similarity +
                    0.15 * minhash_similarity
                )
                
                # Bonus for title matches (titles are more important)
                title_terms = set(re.findall(r'\b\w+\b', title_lower))
                title_matches = query_term_set & title_terms
                if title_matches:
                    title_boost = 0.2 * (len(title_matches) / len(query_term_set))
                    hybrid_score = min(hybrid_score + title_boost, 1.0)
                
                # Bonus for substring match in filename/title (high priority)
                if is_substring_match:
                    # Calculate substring match quality (longer matches = better)
                    substring_boost = 0.3 * (len(query_lower) / max(len(title_lower), 1))
                    substring_boost = min(substring_boost, 0.4)  # Cap at 0.4
                    hybrid_score = min(hybrid_score + substring_boost, 1.0)
                    # If this is ONLY a substring match (no BM25 score), give base score
                    if hybrid_score < 0.1:
                        hybrid_score = 0.5 + substring_boost  # Base score for substring matches
                
                # Get document ID
                doc_id = doc_dict.get("id") or doc_dict.get("_id", "")
                if hasattr(doc_id, '__str__'):
                    doc_id = str(doc_id)
                
                results.append({
                    "document_id": doc_id,
                    "title": doc_dict.get("title", "Untitled"),
                    "content": doc_dict.get("content", ""),
                    "score": round(hybrid_score, 4),
                    "node_id": doc_dict.get("node_id", ""),
                    "metadata": doc_dict.get("metadata", {}),
                    "matched_terms": list(matched_terms),
                    "vectors": doc_dict.get("vectors", {}),
                    "score_breakdown": {
                        "bm25": round(bm25_normalized, 4),
                        "tfidf_similarity": round(vector_similarity, 4),
                        "minhash_similarity": round(minhash_similarity, 4)
                    }
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
        # Try to get persistent count from Redis
        total_searches = self._total_searches
        try:
            r = _get_redis()
            if r:
                redis_count = r.get("distrisearch:total_searches")
                if redis_count:
                    total_searches = int(redis_count)
        except Exception as e:
            logger.warning(f"Failed to get Redis counter: {e}")
        
        return {
            "total_searches": total_searches,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / total_searches if total_searches > 0 else 0,
            "failed_searches": self._failed_searches,
            "cache_size": len(self._cache),
            "config": {
                "search_timeout_sec": self.config.search_timeout_sec,
                "default_page_size": self.config.default_page_size,
                "enable_caching": self.config.enable_caching
            }
        }

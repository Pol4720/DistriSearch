# -*- coding: utf-8 -*-
"""
Result Aggregator - Aggregates and ranks search results from multiple nodes.

Combines results from distributed searches and applies ranking.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RankingStrategy(Enum):
    """Strategies for ranking aggregated results."""
    DISTANCE = "distance"           # Sort by vector distance (ascending)
    RELEVANCE = "relevance"         # Combined relevance score
    RECENCY = "recency"             # Sort by document date
    POPULARITY = "popularity"       # Sort by access count
    HYBRID = "hybrid"               # Weighted combination


@dataclass
class SearchResult:
    """Individual search result from a node."""
    document_id: str
    node_id: str
    distance: float
    relevance_score: float = 0.0
    
    # Document metadata
    filename: str = ""
    file_type: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    # Match details
    matched_keywords: List[str] = field(default_factory=list)
    snippet: str = ""
    highlight_positions: List[Tuple[int, int]] = field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResults:
    """Aggregated results from distributed search."""
    query: str
    results: List[SearchResult]
    total_results: int
    nodes_queried: List[str]
    nodes_responded: List[str]
    
    # Timing
    search_started: datetime = field(default_factory=datetime.utcnow)
    search_completed: Optional[datetime] = None
    total_time_ms: float = 0.0
    
    # Pagination
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    
    # Facets/aggregations
    facets: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    @property
    def result_count(self) -> int:
        return len(self.results)


class ResultAggregator:
    """
    Aggregates and ranks search results from multiple nodes.
    
    Features:
    - Result deduplication
    - Multi-criteria ranking
    - Facet aggregation
    - Score normalization
    """
    
    def __init__(
        self,
        default_strategy: RankingStrategy = RankingStrategy.HYBRID,
        distance_weight: float = 0.6,
        recency_weight: float = 0.2,
        popularity_weight: float = 0.2
    ):
        """
        Initialize result aggregator.
        
        Args:
            default_strategy: Default ranking strategy
            distance_weight: Weight for distance in hybrid ranking
            recency_weight: Weight for recency in hybrid ranking
            popularity_weight: Weight for popularity in hybrid ranking
        """
        self.default_strategy = default_strategy
        self.distance_weight = distance_weight
        self.recency_weight = recency_weight
        self.popularity_weight = popularity_weight
    
    def aggregate(
        self,
        query: str,
        node_results: Dict[str, List[SearchResult]],
        nodes_queried: List[str],
        strategy: Optional[RankingStrategy] = None,
        page: int = 1,
        page_size: int = 20,
        max_results: int = 1000
    ) -> AggregatedResults:
        """
        Aggregate results from multiple nodes.
        
        Args:
            query: Original search query
            node_results: Results per node (node_id -> results)
            nodes_queried: All nodes that were queried
            strategy: Ranking strategy to use
            page: Page number (1-indexed)
            page_size: Results per page
            max_results: Maximum total results
            
        Returns:
            Aggregated results
        """
        strategy = strategy or self.default_strategy
        start_time = datetime.utcnow()
        
        # Flatten and deduplicate results
        all_results = []
        seen_docs = set()
        
        for node_id, results in node_results.items():
            for result in results:
                if result.document_id not in seen_docs:
                    seen_docs.add(result.document_id)
                    all_results.append(result)
                else:
                    # Update existing result if this has better score
                    self._update_existing(all_results, result)
        
        # Calculate relevance scores
        all_results = self._calculate_relevance(all_results, strategy)
        
        # Sort by relevance
        all_results = self._sort_results(all_results, strategy)
        
        # Limit total results
        total_results = len(all_results)
        all_results = all_results[:max_results]
        
        # Build facets
        facets = self._build_facets(all_results)
        
        # Paginate
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_results = all_results[start_idx:end_idx]
        
        end_time = datetime.utcnow()
        
        return AggregatedResults(
            query=query,
            results=page_results,
            total_results=total_results,
            nodes_queried=nodes_queried,
            nodes_responded=list(node_results.keys()),
            search_started=start_time,
            search_completed=end_time,
            total_time_ms=(end_time - start_time).total_seconds() * 1000,
            page=page,
            page_size=page_size,
            has_more=end_idx < len(all_results),
            facets=facets
        )
    
    def _update_existing(
        self,
        results: List[SearchResult],
        new_result: SearchResult
    ) -> None:
        """Update existing result if new one is better."""
        for i, existing in enumerate(results):
            if existing.document_id == new_result.document_id:
                # Keep the one with lower distance (better match)
                if new_result.distance < existing.distance:
                    results[i] = new_result
                break
    
    def _calculate_relevance(
        self,
        results: List[SearchResult],
        strategy: RankingStrategy
    ) -> List[SearchResult]:
        """
        Calculate relevance scores for results.
        
        Args:
            results: Search results
            strategy: Ranking strategy
            
        Returns:
            Results with updated relevance scores
        """
        if not results:
            return results
        
        # Normalize distances to 0-1 range
        distances = [r.distance for r in results]
        min_dist = min(distances) if distances else 0
        max_dist = max(distances) if distances else 1
        dist_range = max_dist - min_dist if max_dist != min_dist else 1
        
        for result in results:
            # Base relevance from distance (inverted, normalized)
            normalized_dist = (result.distance - min_dist) / dist_range
            distance_score = 1.0 - normalized_dist
            
            if strategy == RankingStrategy.DISTANCE:
                result.relevance_score = distance_score
                
            elif strategy == RankingStrategy.RECENCY:
                recency_score = self._calculate_recency_score(result)
                result.relevance_score = recency_score
                
            elif strategy == RankingStrategy.POPULARITY:
                popularity_score = self._calculate_popularity_score(result)
                result.relevance_score = popularity_score
                
            elif strategy in (RankingStrategy.RELEVANCE, RankingStrategy.HYBRID):
                # Hybrid scoring
                recency_score = self._calculate_recency_score(result)
                popularity_score = self._calculate_popularity_score(result)
                
                result.relevance_score = (
                    self.distance_weight * distance_score +
                    self.recency_weight * recency_score +
                    self.popularity_weight * popularity_score
                )
            
            else:
                result.relevance_score = distance_score
        
        return results
    
    def _calculate_recency_score(self, result: SearchResult) -> float:
        """Calculate recency score (newer = higher)."""
        if not result.modified_at:
            return 0.5  # Neutral score if no date
        
        now = datetime.utcnow()
        age_days = (now - result.modified_at).days
        
        # Decay function: score decreases with age
        # Full score for today, ~0.5 after 30 days, ~0.1 after 365 days
        score = np.exp(-age_days / 100)
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _calculate_popularity_score(self, result: SearchResult) -> float:
        """Calculate popularity score from metadata."""
        access_count = result.metadata.get("access_count", 0)
        
        # Log scale to prevent domination by very popular docs
        if access_count <= 0:
            return 0.0
        
        score = np.log1p(access_count) / 10  # Normalize assuming max ~22000 accesses
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _sort_results(
        self,
        results: List[SearchResult],
        strategy: RankingStrategy
    ) -> List[SearchResult]:
        """Sort results by relevance."""
        if strategy == RankingStrategy.DISTANCE:
            # Lower distance = better
            return sorted(results, key=lambda r: r.distance)
        else:
            # Higher relevance = better
            return sorted(results, key=lambda r: r.relevance_score, reverse=True)
    
    def _build_facets(
        self,
        results: List[SearchResult]
    ) -> Dict[str, Dict[str, int]]:
        """
        Build facet aggregations from results.
        
        Args:
            results: Search results
            
        Returns:
            Facets by category
        """
        facets = {
            "file_type": defaultdict(int),
            "node": defaultdict(int),
        }
        
        for result in results:
            if result.file_type:
                facets["file_type"][result.file_type] += 1
            facets["node"][result.node_id] += 1
        
        # Convert to regular dicts and sort by count
        return {
            category: dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
            for category, counts in facets.items()
        }
    
    def merge_paginated_results(
        self,
        existing: AggregatedResults,
        new_results: AggregatedResults
    ) -> AggregatedResults:
        """
        Merge new results into existing paginated results.
        
        Args:
            existing: Existing results
            new_results: New results to merge
            
        Returns:
            Merged results
        """
        # Combine results
        all_results = existing.results + new_results.results
        
        # Deduplicate
        seen = set()
        unique_results = []
        for result in all_results:
            if result.document_id not in seen:
                seen.add(result.document_id)
                unique_results.append(result)
        
        # Update totals
        existing.results = unique_results
        existing.total_results = max(existing.total_results, new_results.total_results)
        existing.nodes_responded = list(set(existing.nodes_responded + new_results.nodes_responded))
        existing.has_more = new_results.has_more
        
        return existing
    
    def highlight_snippets(
        self,
        result: SearchResult,
        query_keywords: List[str],
        context_length: int = 150
    ) -> SearchResult:
        """
        Generate highlighted snippets for a result.
        
        Args:
            result: Search result
            query_keywords: Keywords to highlight
            context_length: Characters of context
            
        Returns:
            Result with updated snippet and highlights
        """
        content = result.metadata.get("content", "")
        if not content:
            return result
        
        # Find keyword positions
        positions = []
        content_lower = content.lower()
        
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            start = 0
            while True:
                pos = content_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                positions.append((pos, pos + len(keyword)))
                start = pos + 1
        
        if not positions:
            # No matches, return beginning of content
            result.snippet = content[:context_length] + "..." if len(content) > context_length else content
            return result
        
        # Sort positions and build snippet around first match
        positions.sort()
        first_pos = positions[0][0]
        
        # Context window
        start = max(0, first_pos - context_length // 2)
        end = min(len(content), first_pos + context_length // 2)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        result.snippet = snippet
        result.highlight_positions = [(p[0] - start, p[1] - start) for p in positions 
                                      if start <= p[0] < end]
        
        return result

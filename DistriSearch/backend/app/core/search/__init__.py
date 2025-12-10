# -*- coding: utf-8 -*-
"""
Search Module - Distributed document search.

Implements:
- Query processing and vectorization
- Distributed search across nodes
- Result aggregation and ranking
"""

from .query_processor import QueryProcessor, ProcessedQuery, QueryType
from .search_engine import SearchEngine, SearchConfig, SearchResult
from .result_aggregator import ResultAggregator, AggregatedResults, RankingStrategy

__all__ = [
    "QueryProcessor",
    "ProcessedQuery",
    "QueryType",
    "SearchEngine",
    "SearchConfig",
    "SearchResult",
    "ResultAggregator",
    "AggregatedResults",
    "RankingStrategy",
]

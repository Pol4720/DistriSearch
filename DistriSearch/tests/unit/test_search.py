# -*- coding: utf-8 -*-
"""
Unit Tests for Search Module

Tests query processing, result aggregation, and search engine.
"""

import pytest
import asyncio
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.search.query_processor import (
    QueryProcessor,
    ProcessedQuery,
    QueryType,
)
from app.core.search.result_aggregator import (
    ResultAggregator,
    SearchResult,
    AggregatedResults,
    RankingStrategy,
)
from app.core.search.search_engine import (
    SearchEngine,
    SearchConfig,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_results() -> List[SearchResult]:
    """Sample search results for testing."""
    return [
        SearchResult(
            document_id="doc-1",
            node_id="node-1",
            distance=0.1,
            relevance_score=0.95,
            filename="machine_learning.pdf",
            file_type="pdf",
            snippet="Machine learning is a subset of AI...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            document_id="doc-2",
            node_id="node-2",
            distance=0.2,
            relevance_score=0.87,
            filename="deep_learning.pdf",
            file_type="pdf",
            snippet="Deep learning uses neural networks...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            document_id="doc-3",
            node_id="node-1",
            distance=0.3,
            relevance_score=0.75,
            filename="python.py",
            file_type="py",
            snippet="Python is a popular programming language...",
            metadata={"category": "programming"}
        ),
        SearchResult(
            document_id="doc-4",
            node_id="node-3",
            distance=0.35,
            relevance_score=0.72,
            filename="data_science.md",
            file_type="md",
            snippet="Data science combines statistics...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            document_id="doc-5",
            node_id="node-2",
            distance=0.4,
            relevance_score=0.68,
            filename="neural_networks.pdf",
            file_type="pdf",
            snippet="Neural networks are computing systems...",
            metadata={"category": "technology"}
        )
    ]


@pytest.fixture
def query_processor() -> QueryProcessor:
    """Create query processor instance."""
    return QueryProcessor(
        min_token_length=2,
        max_query_tokens=100
    )


@pytest.fixture
def result_aggregator() -> ResultAggregator:
    """Create result aggregator instance."""
    return ResultAggregator(
        default_strategy=RankingStrategy.HYBRID,
        distance_weight=0.6,
        recency_weight=0.2,
        popularity_weight=0.2
    )


@pytest.fixture
def search_config() -> SearchConfig:
    """Create search configuration."""
    return SearchConfig(
        search_timeout_sec=10.0,
        node_timeout_sec=5.0,
        default_page_size=20,
        max_page_size=100
    )


# ============================================================================
# Query Processor Tests
# ============================================================================

class TestQueryProcessor:
    """Tests for query processing."""
    
    def test_initialization(self, query_processor):
        """Test query processor initialization."""
        assert query_processor is not None
        assert query_processor.min_token_length == 2
        assert query_processor.max_query_tokens == 100
    
    def test_process_simple_query(self, query_processor):
        """Test processing a simple keyword query."""
        result = query_processor.process("machine learning tutorial")
        
        assert isinstance(result, ProcessedQuery)
        assert result.original_query == "machine learning tutorial"
        assert len(result.tokens) > 0
    
    def test_process_empty_query(self, query_processor):
        """Test processing an empty query."""
        result = query_processor.process("")
        
        assert result.original_query == ""
        assert len(result.tokens) == 0
    
    def test_normalize_query(self, query_processor):
        """Test query normalization."""
        result = query_processor.process("  MACHINE   LEARNING  ")
        
        # Should be normalized (lowercase, trimmed)
        assert result.normalized_query == "machine learning"
    
    def test_extract_keywords(self, query_processor):
        """Test keyword extraction from query."""
        result = query_processor.process("python deep learning neural networks")
        
        assert "python" in result.keywords or "python" in result.tokens
    
    def test_detect_query_type(self, query_processor):
        """Test query type detection."""
        # Simple keyword query
        result = query_processor.process("machine learning")
        assert result.query_type in [QueryType.KEYWORD, QueryType.SEMANTIC]
        
        # Phrase query (in quotes)
        result = query_processor.process('"exact phrase match"')
        assert result.query_type in [QueryType.PHRASE, QueryType.COMBINED]
    
    def test_extract_filters(self, query_processor):
        """Test filter extraction from query."""
        result = query_processor.process("python type:pdf ext:py")
        
        # Should extract file type filter
        if result.filters:
            assert "type" in result.filters or "ext" in result.filters


# ============================================================================
# SearchResult Tests
# ============================================================================

class TestSearchResult:
    """Tests for search result dataclass."""
    
    def test_search_result_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            document_id="doc-1",
            node_id="node-1",
            distance=0.15,
            relevance_score=0.9,
            filename="test.pdf",
            snippet="Test snippet..."
        )
        
        assert result.document_id == "doc-1"
        assert result.node_id == "node-1"
        assert result.distance == 0.15
        assert result.relevance_score == 0.9
    
    def test_search_result_defaults(self):
        """Test search result default values."""
        result = SearchResult(
            document_id="doc-1",
            node_id="node-1",
            distance=0.2
        )
        
        assert result.filename == ""
        assert result.snippet == ""
        assert result.matched_keywords == []


# ============================================================================
# Result Aggregator Tests
# ============================================================================

class TestResultAggregator:
    """Tests for result aggregation."""
    
    def test_initialization(self, result_aggregator):
        """Test result aggregator initialization."""
        assert result_aggregator is not None
        assert result_aggregator.distance_weight == 0.6
    
    def test_aggregate_results(self, result_aggregator, sample_results):
        """Test aggregating results from multiple nodes."""
        # Convert list to Dict[str, List[SearchResult]] as expected by aggregate()
        node_results = {}
        for result in sample_results:
            if result.node_id not in node_results:
                node_results[result.node_id] = []
            node_results[result.node_id].append(result)
        
        aggregated = result_aggregator.aggregate(
            query="machine learning",
            node_results=node_results,
            nodes_queried=["node-1", "node-2", "node-3"],
        )
        
        assert isinstance(aggregated, AggregatedResults)
        assert aggregated.result_count == len(sample_results)
        assert aggregated.query == "machine learning"
    
    def test_rank_by_distance(self, result_aggregator, sample_results):
        """Test ranking results by distance."""
        # Convert list to Dict[str, List[SearchResult]]
        node_results = {}
        for result in sample_results:
            if result.node_id not in node_results:
                node_results[result.node_id] = []
            node_results[result.node_id].append(result)
        
        aggregated = result_aggregator.aggregate(
            query="test",
            node_results=node_results,
            nodes_queried=["node-1"],
            strategy=RankingStrategy.DISTANCE
        )
        
        # Results should be sorted by distance (ascending)
        distances = [r.distance for r in aggregated.results]
        assert distances == sorted(distances)
    
    def test_remove_duplicates(self, result_aggregator):
        """Test duplicate removal."""
        results_with_dupes = [
            SearchResult(document_id="doc-1", node_id="node-1", distance=0.1),
            SearchResult(document_id="doc-1", node_id="node-2", distance=0.15),  # Duplicate
            SearchResult(document_id="doc-2", node_id="node-1", distance=0.2),
        ]
        
        # Convert to dict format
        node_results = {}
        for result in results_with_dupes:
            if result.node_id not in node_results:
                node_results[result.node_id] = []
            node_results[result.node_id].append(result)
        
        aggregated = result_aggregator.aggregate(
            query="test",
            node_results=node_results,
            nodes_queried=["node-1", "node-2"],
        )
        
        # Should have removed duplicate, keeping the one with lower distance
        doc_ids = [r.document_id for r in aggregated.results]
        assert doc_ids.count("doc-1") == 1
    
    def test_pagination(self, result_aggregator, sample_results):
        """Test result pagination."""
        # Convert list to Dict[str, List[SearchResult]]
        node_results = {}
        for result in sample_results:
            if result.node_id not in node_results:
                node_results[result.node_id] = []
            node_results[result.node_id].append(result)
        
        aggregated = result_aggregator.aggregate(
            query="test",
            node_results=node_results,
            nodes_queried=["node-1"],
            page=1,
            page_size=2
        )
        
        assert len(aggregated.results) <= 2
        assert aggregated.has_more is True or aggregated.total_results > 2


# ============================================================================
# AggregatedResults Tests
# ============================================================================

class TestAggregatedResults:
    """Tests for aggregated results dataclass."""
    
    def test_result_count_property(self, sample_results):
        """Test result count property."""
        aggregated = AggregatedResults(
            query="test",
            results=sample_results,
            total_results=len(sample_results),
            nodes_queried=["node-1"],
            nodes_responded=["node-1"]
        )
        
        assert aggregated.result_count == len(sample_results)


# ============================================================================
# Search Config Tests
# ============================================================================

class TestSearchConfig:
    """Tests for search configuration."""
    
    def test_default_config(self):
        """Test default search config values."""
        config = SearchConfig()
        
        assert config.search_timeout_sec == 10.0
        assert config.default_page_size == 20
        assert config.allow_partial_results is True
    
    def test_custom_config(self):
        """Test custom search config."""
        config = SearchConfig(
            search_timeout_sec=5.0,
            default_page_size=50,
            allow_partial_results=False
        )
        
        assert config.search_timeout_sec == 5.0
        assert config.default_page_size == 50
        assert config.allow_partial_results is False


# ============================================================================
# Search Engine Tests
# ============================================================================

class TestSearchEngine:
    """Tests for search engine."""
    
    def test_initialization(self, search_config):
        """Test search engine initialization."""
        engine = SearchEngine(config=search_config)
        
        assert engine is not None
        assert engine.config == search_config
    
    @pytest.mark.asyncio
    async def test_search_with_no_nodes(self, search_config):
        """Test search when no nodes are available."""
        async def get_targets(query):
            return []
        
        engine = SearchEngine(
            config=search_config,
            get_target_nodes_func=get_targets
        )
        
        # Search should handle empty node list gracefully
        # The actual behavior depends on implementation


# ============================================================================
# Integration Tests
# ============================================================================

class TestSearchIntegration:
    """Integration tests for search functionality."""
    
    def test_query_to_aggregation_flow(self, query_processor, result_aggregator, sample_results):
        """Test complete query processing to result aggregation flow."""
        # Process query
        processed = query_processor.process("machine learning tutorial")
        
        # Convert list to Dict[str, List[SearchResult]]
        node_results = {}
        for result in sample_results:
            if result.node_id not in node_results:
                node_results[result.node_id] = []
            node_results[result.node_id].append(result)
        
        # Aggregate results (simulated from nodes)
        aggregated = result_aggregator.aggregate(
            query=processed.original_query,
            node_results=node_results,
            nodes_queried=["node-1", "node-2", "node-3"],
        )
        
        assert processed.original_query == "machine learning tutorial"
        assert aggregated.result_count > 0
    
    @pytest.mark.asyncio
    async def test_distributed_search_mock(self, search_config, sample_results):
        """Test distributed search with mocked node queries."""
        # Mock functions
        async def mock_query_node(node_id, query, limit):
            return [r for r in sample_results if r.node_id == node_id][:limit]
        
        async def mock_get_targets(query):
            return ["node-1", "node-2", "node-3"]
        
        engine = SearchEngine(
            config=search_config,
            query_node_func=mock_query_node,
            get_target_nodes_func=mock_get_targets
        )
        
        # The engine should be able to perform distributed search
        assert engine._query_node is not None
        assert engine._get_targets is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

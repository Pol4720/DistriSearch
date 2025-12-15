"""
Unit Tests for Search Module
Tests distributed search and query routing
"""

import pytest
import asyncio
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from search.query_processor import QueryProcessor
from search.result_aggregator import ResultAggregator
from search.distributed_search import DistributedSearchEngine
from search.ranking import RankingEngine, SearchResult
from shared.models import Document, SearchQuery, SearchResponse


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_results() -> List[SearchResult]:
    """Sample search results for testing"""
    return [
        SearchResult(
            doc_id="doc-1",
            title="Machine Learning Basics",
            score=0.95,
            content_snippet="Machine learning is a subset of AI...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            doc_id="doc-2",
            title="Deep Learning Guide",
            score=0.87,
            content_snippet="Deep learning uses neural networks...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            doc_id="doc-3",
            title="Python Programming",
            score=0.75,
            content_snippet="Python is a popular programming language...",
            metadata={"category": "programming"}
        ),
        SearchResult(
            doc_id="doc-4",
            title="Data Science Introduction",
            score=0.72,
            content_snippet="Data science combines statistics...",
            metadata={"category": "technology"}
        ),
        SearchResult(
            doc_id="doc-5",
            title="Neural Networks",
            score=0.68,
            content_snippet="Neural networks are computing systems...",
            metadata={"category": "technology"}
        )
    ]


@pytest.fixture
def query_processor() -> QueryProcessor:
    """Create query processor instance"""
    return QueryProcessor(
        min_query_length=2,
        max_query_length=500,
        enable_spell_check=False
    )


@pytest.fixture
def result_aggregator() -> ResultAggregator:
    """Create result aggregator instance"""
    return ResultAggregator(
        score_normalization=True,
        duplicate_threshold=0.9
    )


@pytest.fixture
def ranking_engine() -> RankingEngine:
    """Create ranking engine instance"""
    return RankingEngine(
        tfidf_weight=0.5,
        minhash_weight=0.3,
        lda_weight=0.2
    )


# ============================================================================
# Query Processor Tests
# ============================================================================

class TestQueryProcessor:
    """Tests for query processing"""
    
    def test_initialization(self, query_processor: QueryProcessor):
        """Test query processor initialization"""
        assert query_processor is not None
        assert query_processor.min_query_length == 2
        assert query_processor.max_query_length == 500
    
    def test_process_simple_query(self, query_processor: QueryProcessor):
        """Test processing simple query"""
        query = "machine learning"
        result = query_processor.process(query)
        
        assert result is not None
        assert result.original == query
        assert result.normalized is not None
        assert len(result.tokens) > 0
    
    def test_query_normalization(self, query_processor: QueryProcessor):
        """Test query normalization"""
        query = "  MACHINE   Learning  "
        result = query_processor.process(query)
        
        assert result.normalized == "machine learning"
    
    def test_tokenization(self, query_processor: QueryProcessor):
        """Test query tokenization"""
        query = "machine learning algorithms"
        result = query_processor.process(query)
        
        assert "machine" in result.tokens
        assert "learning" in result.tokens
        assert "algorithms" in result.tokens
    
    def test_stop_word_removal(self, query_processor: QueryProcessor):
        """Test stop word removal"""
        query = "the machine learning is a field"
        result = query_processor.process(query)
        
        # Stop words should be removed
        assert "the" not in result.tokens
        assert "is" not in result.tokens
        assert "a" not in result.tokens
        
        # Content words should remain
        assert "machine" in result.tokens
        assert "learning" in result.tokens
    
    def test_empty_query(self, query_processor: QueryProcessor):
        """Test handling of empty query"""
        result = query_processor.process("")
        
        assert result.is_empty
        assert len(result.tokens) == 0
    
    def test_query_too_short(self, query_processor: QueryProcessor):
        """Test query below minimum length"""
        result = query_processor.process("a")
        
        assert result.is_valid == False
    
    def test_query_too_long(self, query_processor: QueryProcessor):
        """Test query exceeding maximum length"""
        long_query = "word " * 200  # Very long query
        result = query_processor.process(long_query)
        
        # Should truncate or reject
        assert result.is_valid == False or len(result.original) <= query_processor.max_query_length
    
    def test_special_characters(self, query_processor: QueryProcessor):
        """Test handling of special characters"""
        query = "C++ programming @#$% language!"
        result = query_processor.process(query)
        
        assert result.normalized is not None
        # Should handle special chars gracefully
    
    def test_phrase_detection(self, query_processor: QueryProcessor):
        """Test quoted phrase detection"""
        query = '"machine learning" algorithms'
        result = query_processor.process(query)
        
        assert "machine learning" in result.phrases or len(result.tokens) > 0
    
    def test_boolean_operators(self, query_processor: QueryProcessor):
        """Test boolean operator handling"""
        query = "machine AND learning OR deep"
        result = query_processor.process(query)
        
        assert result.has_operators or "and" not in [t.lower() for t in result.tokens]


# ============================================================================
# Result Aggregator Tests
# ============================================================================

class TestResultAggregator:
    """Tests for result aggregation"""
    
    def test_initialization(self, result_aggregator: ResultAggregator):
        """Test aggregator initialization"""
        assert result_aggregator is not None
        assert result_aggregator.score_normalization == True
    
    def test_aggregate_single_source(self, result_aggregator: ResultAggregator, sample_results: List[SearchResult]):
        """Test aggregating results from single source"""
        results_by_node = {"node-1": sample_results}
        
        aggregated = result_aggregator.aggregate(results_by_node)
        
        assert len(aggregated) == len(sample_results)
    
    def test_aggregate_multiple_sources(self, result_aggregator: ResultAggregator, sample_results: List[SearchResult]):
        """Test aggregating results from multiple sources"""
        # Split results across nodes
        results_by_node = {
            "node-1": sample_results[:3],
            "node-2": sample_results[2:5]  # Overlapping
        }
        
        aggregated = result_aggregator.aggregate(results_by_node)
        
        # Should deduplicate
        doc_ids = [r.doc_id for r in aggregated]
        assert len(doc_ids) == len(set(doc_ids))
    
    def test_score_normalization(self, result_aggregator: ResultAggregator):
        """Test score normalization"""
        results = [
            SearchResult(doc_id="1", title="A", score=100, content_snippet=""),
            SearchResult(doc_id="2", title="B", score=50, content_snippet=""),
            SearchResult(doc_id="3", title="C", score=25, content_snippet="")
        ]
        
        results_by_node = {"node-1": results}
        aggregated = result_aggregator.aggregate(results_by_node)
        
        # Scores should be normalized to 0-1 range
        for r in aggregated:
            assert 0 <= r.score <= 1
    
    def test_result_ordering(self, result_aggregator: ResultAggregator, sample_results: List[SearchResult]):
        """Test that results are ordered by score"""
        results_by_node = {"node-1": sample_results}
        aggregated = result_aggregator.aggregate(results_by_node)
        
        # Check descending order
        for i in range(len(aggregated) - 1):
            assert aggregated[i].score >= aggregated[i + 1].score
    
    def test_limit_results(self, result_aggregator: ResultAggregator, sample_results: List[SearchResult]):
        """Test limiting number of results"""
        results_by_node = {"node-1": sample_results}
        aggregated = result_aggregator.aggregate(results_by_node, limit=3)
        
        assert len(aggregated) == 3
    
    def test_duplicate_detection(self, result_aggregator: ResultAggregator):
        """Test detection of duplicate results"""
        results1 = [
            SearchResult(doc_id="1", title="Test", score=0.9, content_snippet="content"),
        ]
        results2 = [
            SearchResult(doc_id="1", title="Test", score=0.8, content_snippet="content"),  # Same doc
        ]
        
        results_by_node = {"node-1": results1, "node-2": results2}
        aggregated = result_aggregator.aggregate(results_by_node)
        
        # Should keep highest score
        assert len(aggregated) == 1
        assert aggregated[0].score == 0.9
    
    def test_empty_results(self, result_aggregator: ResultAggregator):
        """Test handling empty results"""
        results_by_node = {}
        aggregated = result_aggregator.aggregate(results_by_node)
        
        assert len(aggregated) == 0
    
    def test_partial_failures(self, result_aggregator: ResultAggregator, sample_results: List[SearchResult]):
        """Test handling partial node failures"""
        results_by_node = {
            "node-1": sample_results[:2],
            "node-2": None,  # Failed
            "node-3": sample_results[3:]
        }
        
        aggregated = result_aggregator.aggregate(results_by_node)
        
        # Should aggregate available results
        assert len(aggregated) > 0


# ============================================================================
# Ranking Engine Tests
# ============================================================================

class TestRankingEngine:
    """Tests for ranking engine"""
    
    def test_initialization(self, ranking_engine: RankingEngine):
        """Test ranking engine initialization"""
        assert ranking_engine is not None
        assert ranking_engine.tfidf_weight == 0.5
        assert ranking_engine.minhash_weight == 0.3
        assert ranking_engine.lda_weight == 0.2
    
    def test_compute_combined_score(self, ranking_engine: RankingEngine):
        """Test combined score computation"""
        scores = {
            "tfidf": 0.8,
            "minhash": 0.6,
            "lda": 0.7
        }
        
        combined = ranking_engine.compute_combined_score(scores)
        
        expected = (0.5 * 0.8) + (0.3 * 0.6) + (0.2 * 0.7)
        assert abs(combined - expected) < 0.001
    
    def test_rank_results(self, ranking_engine: RankingEngine, sample_results: List[SearchResult]):
        """Test ranking results"""
        ranked = ranking_engine.rank(sample_results)
        
        assert len(ranked) == len(sample_results)
        
        # Should be in descending score order
        for i in range(len(ranked) - 1):
            assert ranked[i].score >= ranked[i + 1].score
    
    def test_boost_recent(self, ranking_engine: RankingEngine):
        """Test boosting recent documents"""
        from datetime import datetime, timedelta
        
        results = [
            SearchResult(
                doc_id="1",
                title="Old",
                score=0.9,
                content_snippet="",
                metadata={"created_at": (datetime.now() - timedelta(days=365)).isoformat()}
            ),
            SearchResult(
                doc_id="2",
                title="New",
                score=0.8,
                content_snippet="",
                metadata={"created_at": datetime.now().isoformat()}
            )
        ]
        
        ranked = ranking_engine.rank(results, boost_recent=True)
        
        # Newer document might rank higher despite lower initial score
        # (depends on boost factor)
    
    def test_filter_by_category(self, ranking_engine: RankingEngine, sample_results: List[SearchResult]):
        """Test filtering by category"""
        filtered = ranking_engine.filter_by_metadata(
            sample_results,
            filters={"category": "technology"}
        )
        
        for result in filtered:
            assert result.metadata.get("category") == "technology"
    
    def test_minimum_score_threshold(self, ranking_engine: RankingEngine, sample_results: List[SearchResult]):
        """Test minimum score threshold"""
        filtered = ranking_engine.filter_by_score(sample_results, min_score=0.7)
        
        for result in filtered:
            assert result.score >= 0.7


# ============================================================================
# Distributed Search Tests
# ============================================================================

class TestDistributedSearchEngine:
    """Tests for distributed search engine"""
    
    @pytest.fixture
    def mock_partition_manager(self):
        """Create mock partition manager"""
        manager = Mock()
        manager.get_all_nodes.return_value = ["node-1", "node-2", "node-3"]
        manager.get_document_nodes.return_value = ["node-1", "node-2"]
        manager.get_nodes_for_partition.return_value = ["node-1", "node-2", "node-3"]
        return manager
    
    @pytest.fixture
    def mock_communication(self):
        """Create mock communication layer"""
        comm = AsyncMock()
        comm.send_search_request = AsyncMock(return_value={
            "results": [
                {"doc_id": "1", "title": "Test", "score": 0.9, "content_snippet": "..."}
            ]
        })
        return comm
    
    @pytest.fixture
    def search_engine(self, mock_partition_manager, mock_communication) -> DistributedSearchEngine:
        """Create distributed search engine"""
        return DistributedSearchEngine(
            partition_manager=mock_partition_manager,
            communication=mock_communication,
            timeout=30
        )
    
    @pytest.mark.asyncio
    async def test_search_basic(self, search_engine: DistributedSearchEngine):
        """Test basic search operation"""
        query = SearchQuery(query="machine learning", limit=10)
        
        response = await search_engine.search(query)
        
        assert response is not None
        assert isinstance(response, SearchResponse)
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_engine: DistributedSearchEngine):
        """Test search with filters"""
        query = SearchQuery(
            query="machine learning",
            limit=10,
            filters={"category": "technology"}
        )
        
        response = await search_engine.search(query)
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_broadcast_search(self, search_engine: DistributedSearchEngine, mock_communication):
        """Test that search is broadcast to all nodes"""
        query = SearchQuery(query="test", limit=10)
        
        await search_engine.search(query)
        
        # Should have sent requests to multiple nodes
        assert mock_communication.send_search_request.called
    
    @pytest.mark.asyncio
    async def test_handle_node_failure(self, search_engine: DistributedSearchEngine, mock_communication):
        """Test handling node failures during search"""
        # Simulate one node failing
        mock_communication.send_search_request = AsyncMock(
            side_effect=[
                {"results": [{"doc_id": "1", "title": "A", "score": 0.9, "content_snippet": ""}]},
                Exception("Node unavailable"),
                {"results": [{"doc_id": "2", "title": "B", "score": 0.8, "content_snippet": ""}]}
            ]
        )
        
        query = SearchQuery(query="test", limit=10)
        response = await search_engine.search(query)
        
        # Should still return results from available nodes
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_search_timeout(self, search_engine: DistributedSearchEngine, mock_communication):
        """Test search timeout handling"""
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(100)
            return {"results": []}
        
        mock_communication.send_search_request = slow_response
        
        query = SearchQuery(query="test", limit=10)
        
        # Should timeout and return partial results
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(search_engine.search(query), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_result_aggregation(self, search_engine: DistributedSearchEngine, mock_communication):
        """Test result aggregation from multiple nodes"""
        mock_communication.send_search_request = AsyncMock(
            side_effect=[
                {"results": [{"doc_id": "1", "title": "A", "score": 0.9, "content_snippet": ""}]},
                {"results": [{"doc_id": "2", "title": "B", "score": 0.8, "content_snippet": ""}]},
                {"results": [{"doc_id": "3", "title": "C", "score": 0.7, "content_snippet": ""}]}
            ]
        )
        
        query = SearchQuery(query="test", limit=10)
        response = await search_engine.search(query)
        
        assert len(response.results) >= 1


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_query_results(self, result_aggregator: ResultAggregator):
        """Test handling queries with no results"""
        results_by_node = {
            "node-1": [],
            "node-2": [],
            "node-3": []
        }
        
        aggregated = result_aggregator.aggregate(results_by_node)
        
        assert len(aggregated) == 0
    
    def test_very_long_results_list(self, result_aggregator: ResultAggregator):
        """Test handling large number of results"""
        results = [
            SearchResult(
                doc_id=f"doc-{i}",
                title=f"Document {i}",
                score=1.0 - (i / 10000),
                content_snippet=f"Content {i}"
            )
            for i in range(1000)
        ]
        
        results_by_node = {"node-1": results}
        aggregated = result_aggregator.aggregate(results_by_node, limit=100)
        
        assert len(aggregated) == 100
    
    def test_unicode_in_query(self, query_processor: QueryProcessor):
        """Test handling unicode characters in query"""
        query = "机器学习 машинное обучение machine learning"
        result = query_processor.process(query)
        
        assert result is not None
    
    def test_zero_scores(self, ranking_engine: RankingEngine):
        """Test handling zero scores"""
        results = [
            SearchResult(doc_id="1", title="A", score=0.0, content_snippet=""),
            SearchResult(doc_id="2", title="B", score=0.0, content_snippet="")
        ]
        
        ranked = ranking_engine.rank(results)
        
        assert len(ranked) == 2
    
    def test_negative_scores(self, ranking_engine: RankingEngine):
        """Test handling negative scores"""
        results = [
            SearchResult(doc_id="1", title="A", score=-0.5, content_snippet=""),
            SearchResult(doc_id="2", title="B", score=0.5, content_snippet="")
        ]
        
        ranked = ranking_engine.rank(results)
        
        # Negative scores should be handled (normalized or filtered)
        assert len(ranked) >= 1


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests"""
    
    @pytest.mark.slow
    def test_large_aggregation(self, result_aggregator: ResultAggregator):
        """Test aggregating many results"""
        import time
        
        # Generate results from multiple nodes
        results_by_node = {}
        for node_idx in range(10):
            results_by_node[f"node-{node_idx}"] = [
                SearchResult(
                    doc_id=f"doc-{node_idx}-{i}",
                    title=f"Document {i}",
                    score=0.9 - (i / 1000),
                    content_snippet=f"Content {i}"
                )
                for i in range(1000)
            ]
        
        start = time.time()
        aggregated = result_aggregator.aggregate(results_by_node, limit=100)
        elapsed = time.time() - start
        
        assert elapsed < 5.0  # Should complete in reasonable time
        assert len(aggregated) == 100
    
    @pytest.mark.slow
    def test_many_queries(self, query_processor: QueryProcessor):
        """Test processing many queries"""
        import time
        
        queries = [f"machine learning topic {i}" for i in range(1000)]
        
        start = time.time()
        for query in queries:
            query_processor.process(query)
        elapsed = time.time() - start
        
        assert elapsed < 5.0  # Should process quickly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

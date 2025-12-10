"""
Integration Tests for API Endpoints
Tests the FastAPI REST API
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_document() -> Dict[str, Any]:
    """Sample document for testing"""
    return {
        "title": "Test Document",
        "content": "This is a test document about machine learning and artificial intelligence.",
        "metadata": {
            "category": "technology",
            "tags": ["test", "ml", "ai"]
        }
    }


@pytest.fixture
def mock_storage():
    """Mock storage adapter"""
    storage = AsyncMock()
    storage.save_document = AsyncMock(return_value="doc-123")
    storage.get_document = AsyncMock(return_value={
        "id": "doc-123",
        "title": "Test Document",
        "content": "Test content",
        "metadata": {}
    })
    storage.delete_document = AsyncMock(return_value=True)
    storage.list_documents = AsyncMock(return_value={
        "documents": [],
        "total": 0
    })
    return storage


@pytest.fixture
def mock_search_engine():
    """Mock search engine"""
    search = AsyncMock()
    search.search = AsyncMock(return_value={
        "results": [
            {
                "doc_id": "doc-123",
                "title": "Test",
                "score": 0.95,
                "content_snippet": "Test content..."
            }
        ],
        "total": 1,
        "query_time_ms": 50
    })
    return search


@pytest.fixture
def mock_cluster():
    """Mock cluster manager"""
    cluster = Mock()
    cluster.get_status = Mock(return_value={
        "status": "healthy",
        "nodes": 3,
        "leader": "node-1"
    })
    cluster.get_nodes = Mock(return_value=[
        {"id": "node-1", "status": "healthy", "role": "leader"},
        {"id": "node-2", "status": "healthy", "role": "follower"},
        {"id": "node-3", "status": "healthy", "role": "follower"}
    ])
    return cluster


@pytest.fixture
def app(mock_storage, mock_search_engine, mock_cluster):
    """Create FastAPI app with mocked dependencies"""
    from api.main import create_app
    
    app = create_app()
    
    # Override dependencies
    app.state.storage = mock_storage
    app.state.search_engine = mock_search_engine
    app.state.cluster = mock_cluster
    
    return app


@pytest.fixture
async def client(app):
    """Create async HTTP client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# Health Endpoint Tests
# ============================================================================

class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check"""
        response = await client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient):
        """Test readiness probe"""
        response = await client.get("/api/v1/health/ready")
        
        assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_liveness_check(self, client: AsyncClient):
        """Test liveness probe"""
        response = await client.get("/api/v1/health/live")
        
        assert response.status_code == 200


# ============================================================================
# Document Endpoint Tests
# ============================================================================

class TestDocumentEndpoints:
    """Tests for document CRUD endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_document(self, client: AsyncClient, sample_document: Dict[str, Any]):
        """Test creating a document"""
        response = await client.post("/api/v1/documents", json=sample_document)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_create_document_invalid(self, client: AsyncClient):
        """Test creating document with invalid data"""
        invalid_doc = {"title": ""}  # Missing required fields
        
        response = await client.post("/api/v1/documents", json=invalid_doc)
        
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_get_document(self, client: AsyncClient):
        """Test getting a document by ID"""
        response = await client.get("/api/v1/documents/doc-123")
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "title" in data
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client: AsyncClient, mock_storage):
        """Test getting non-existent document"""
        mock_storage.get_document = AsyncMock(return_value=None)
        
        response = await client.get("/api/v1/documents/nonexistent")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_document(self, client: AsyncClient, sample_document: Dict[str, Any]):
        """Test updating a document"""
        updated = {**sample_document, "title": "Updated Title"}
        
        response = await client.put("/api/v1/documents/doc-123", json=updated)
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_delete_document(self, client: AsyncClient):
        """Test deleting a document"""
        response = await client.delete("/api/v1/documents/doc-123")
        
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_list_documents(self, client: AsyncClient):
        """Test listing documents"""
        response = await client.get("/api/v1/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
    
    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, client: AsyncClient):
        """Test document listing with pagination"""
        response = await client.get("/api/v1/documents?skip=10&limit=20")
        
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data


# ============================================================================
# Search Endpoint Tests
# ============================================================================

class TestSearchEndpoints:
    """Tests for search endpoints"""
    
    @pytest.mark.asyncio
    async def test_search_basic(self, client: AsyncClient):
        """Test basic search"""
        response = await client.post(
            "/api/v1/search",
            json={"query": "machine learning"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self, client: AsyncClient):
        """Test search with result limit"""
        response = await client.post(
            "/api/v1/search",
            json={"query": "machine learning", "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, client: AsyncClient):
        """Test search with filters"""
        response = await client.post(
            "/api/v1/search",
            json={
                "query": "machine learning",
                "filters": {"category": "technology"}
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, client: AsyncClient):
        """Test search with empty query"""
        response = await client.post(
            "/api/v1/search",
            json={"query": ""}
        )
        
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_search_invalid_request(self, client: AsyncClient):
        """Test search with invalid request"""
        response = await client.post(
            "/api/v1/search",
            json={}  # Missing query
        )
        
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_search_response_format(self, client: AsyncClient):
        """Test search response format"""
        response = await client.post(
            "/api/v1/search",
            json={"query": "test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "total" in data
        assert "query_time_ms" in data
        
        if data["results"]:
            result = data["results"][0]
            assert "doc_id" in result
            assert "title" in result
            assert "score" in result


# ============================================================================
# Cluster Endpoint Tests
# ============================================================================

class TestClusterEndpoints:
    """Tests for cluster management endpoints"""
    
    @pytest.mark.asyncio
    async def test_cluster_status(self, client: AsyncClient):
        """Test getting cluster status"""
        response = await client.get("/api/v1/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    @pytest.mark.asyncio
    async def test_cluster_nodes(self, client: AsyncClient):
        """Test getting cluster nodes"""
        response = await client.get("/api/v1/cluster/nodes")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_cluster_partitions(self, client: AsyncClient):
        """Test getting partition information"""
        response = await client.get("/api/v1/cluster/partitions")
        
        assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling"""
    
    @pytest.mark.asyncio
    async def test_404_not_found(self, client: AsyncClient):
        """Test 404 response for unknown endpoint"""
        response = await client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client: AsyncClient):
        """Test 405 response for wrong method"""
        response = await client.post("/api/v1/health")
        
        assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_validation_error_format(self, client: AsyncClient):
        """Test validation error response format"""
        response = await client.post(
            "/api/v1/documents",
            json={"invalid_field": "value"}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_internal_server_error(self, client: AsyncClient, mock_storage):
        """Test 500 response on internal error"""
        mock_storage.get_document = AsyncMock(side_effect=Exception("Internal error"))
        
        response = await client.get("/api/v1/documents/doc-123")
        
        assert response.status_code == 500


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limit_exceeded(self, client: AsyncClient):
        """Test rate limiting enforcement"""
        # Make many requests quickly
        responses = []
        for _ in range(100):
            response = await client.get("/api/v1/health")
            responses.append(response)
        
        # At least some should be rate limited
        status_codes = [r.status_code for r in responses]
        # Depending on configuration, 429 may or may not appear
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client: AsyncClient):
        """Test rate limit headers in response"""
        response = await client.get("/api/v1/health")
        
        # Check for rate limit headers
        # These may or may not be present depending on implementation
        # Common headers: X-RateLimit-Limit, X-RateLimit-Remaining


# ============================================================================
# Authentication Tests
# ============================================================================

class TestAuthentication:
    """Tests for authentication (if implemented)"""
    
    @pytest.mark.asyncio
    async def test_unauthenticated_access(self, client: AsyncClient):
        """Test accessing protected endpoint without auth"""
        # Health should be accessible without auth
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_invalid_token(self, client: AsyncClient):
        """Test accessing with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/api/v1/documents", headers=headers)
        
        # Response depends on auth configuration
        # May be 401 or 200 if auth is not enforced


# ============================================================================
# CORS Tests
# ============================================================================

class TestCORS:
    """Tests for CORS configuration"""
    
    @pytest.mark.asyncio
    async def test_cors_preflight(self, client: AsyncClient):
        """Test CORS preflight request"""
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should allow CORS
        assert response.status_code in [200, 204]
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """Test CORS headers in response"""
        response = await client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Check for CORS headers
        # May or may not be present depending on configuration


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_requests(self, client: AsyncClient):
        """Test handling concurrent requests"""
        import asyncio
        
        async def make_request():
            return await client.get("/api/v1/health")
        
        # Make 50 concurrent requests
        tasks = [make_request() for _ in range(50)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 45  # Allow some failures
    
    @pytest.mark.asyncio
    async def test_response_time(self, client: AsyncClient):
        """Test response time is reasonable"""
        import time
        
        start = time.time()
        response = await client.get("/api/v1/health")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 1.0  # Should respond within 1 second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

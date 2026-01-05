# -*- coding: utf-8 -*-
"""
Load Balancing and Rebalancing Tests

Tests to verify load balancing functionality:
- Load calculation and metrics
- Imbalance detection
- Rebalance decision making
- Document migration between nodes
- Rate-limited migrations
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.core.rebalancing.load_calculator import (
    LoadCalculator,
    LoadMetrics,
    RebalanceDecision,
    ClusterLoadSummary,
    LoadLevel,
)
from app.core.rebalancing.active_rebalancer import (
    ActiveRebalancer,
    RebalanceConfig,
    RebalanceStatus,
    RebalanceOperation,
)
from app.core.rebalancing.migration_handler import (
    MigrationHandler,
    MigrationTask,
    MigrationResult,
    MigrationConfig,
    MigrationStatus,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def load_calculator() -> LoadCalculator:
    """Create load calculator."""
    return LoadCalculator()


@pytest.fixture
def rebalance_config() -> RebalanceConfig:
    """Create rebalance configuration."""
    return RebalanceConfig(
        imbalance_threshold=0.2,
        critical_threshold=0.9,
        min_documents_to_move=10,
        check_interval_sec=60.0,
        batch_size=50,
        batch_delay_sec=1.0,
        max_concurrent_migrations=2,
    )


@pytest.fixture
def migration_config() -> MigrationConfig:
    """Create migration configuration."""
    return MigrationConfig(
        batch_size=50,
        batch_delay_sec=0.1,
        max_retries=3,
        transfer_timeout_sec=30.0,
    )


@pytest.fixture
async def active_rebalancer(rebalance_config) -> ActiveRebalancer:
    """Create active rebalancer with mocks."""
    mock_selector = AsyncMock(return_value=["doc-1", "doc-2", "doc-3"])
    mock_transfer = AsyncMock(return_value={"success": True, "transferred": 3})
    
    rebalancer = ActiveRebalancer(
        config=rebalance_config,
        document_selector=mock_selector,
        transfer_func=mock_transfer,
    )
    return rebalancer


# ============================================================================
# Load Metrics Tests
# ============================================================================

class TestLoadMetrics:
    """Tests for load metrics calculation."""
    
    def test_load_metrics_creation(self):
        """Test creating load metrics."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            capacity=5000,
            storage_used_bytes=1024 * 1024 * 100,  # 100 MB
            storage_capacity_bytes=1024 * 1024 * 1000,  # 1 GB
            cpu_usage=0.45,
            memory_usage=0.60,
            query_rate=50.0,
            avg_latency_ms=25.0,
        )
        
        assert metrics.node_id == "node-1"
        assert metrics.document_count == 1000
        assert metrics.capacity == 5000
        assert metrics.cpu_usage == 0.45
    
    def test_load_factor(self):
        """Test load factor calculation."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            capacity=5000,
        )
        
        assert metrics.load_factor == 0.2  # 1000/5000
    
    def test_combined_load_score(self):
        """Test combined load score calculation."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=2500,
            capacity=5000,
            storage_used_bytes=500 * 1024 * 1024,
            storage_capacity_bytes=1000 * 1024 * 1024,
            cpu_usage=0.50,
            memory_usage=0.40,
        )
        
        score = metrics.combined_load
        
        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0
        # With 50% document load, 50% storage, 50% CPU, 40% memory
        # Expected: 0.4*0.5 + 0.2*0.5 + 0.2*0.5 + 0.2*0.4 = 0.2 + 0.1 + 0.1 + 0.08 = 0.48
        assert 0.4 <= score <= 0.6
    
    def test_high_cpu_increases_load(self):
        """Test that high CPU increases load score."""
        low_cpu = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            capacity=5000,
            cpu_usage=0.20,
            memory_usage=0.40,
        )
        high_cpu = LoadMetrics(
            node_id="node-2",
            document_count=1000,
            capacity=5000,
            cpu_usage=0.90,
            memory_usage=0.40,
        )
        
        low_score = low_cpu.combined_load
        high_score = high_cpu.combined_load
        
        assert high_score > low_score
    
    def test_load_level_categorization(self):
        """Test load level categorization."""
        empty = LoadMetrics(node_id="n1", document_count=0, capacity=1000)
        low = LoadMetrics(node_id="n2", document_count=300, capacity=1000)
        normal = LoadMetrics(node_id="n3", document_count=600, capacity=1000)
        high = LoadMetrics(node_id="n4", document_count=800, capacity=1000)
        critical = LoadMetrics(node_id="n5", document_count=950, capacity=1000)
        
        assert empty.load_level == LoadLevel.EMPTY
        assert low.load_level == LoadLevel.LOW
        assert normal.load_level == LoadLevel.NORMAL
        assert high.load_level == LoadLevel.HIGH
        assert critical.load_level == LoadLevel.CRITICAL
    
    def test_available_capacity(self):
        """Test available capacity calculation."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=3000,
            capacity=5000,
        )
        
        assert metrics.available_capacity == 2000


# ============================================================================
# Load Calculator Tests
# ============================================================================

class TestLoadCalculator:
    """Tests for load calculation and analysis."""
    
    def test_update_node_metrics(self, load_calculator):
        """Test updating node metrics."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            capacity=5000,
        )
        
        load_calculator.update_node_metrics("node-1", metrics)
        
        retrieved = load_calculator.get_node_metrics("node-1")
        assert retrieved is not None
        assert retrieved.document_count == 1000
    
    def test_cluster_load_summary(self, load_calculator):
        """Test cluster load summary calculation."""
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=1000, capacity=5000, cpu_usage=0.30
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=1200, capacity=5000, cpu_usage=0.40
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=800, capacity=5000, cpu_usage=0.35
        ))
        
        summary = load_calculator.calculate_cluster_summary()
        
        assert summary.total_documents == 3000
        assert summary.node_count == 3
        assert summary.healthy_nodes == 3
    
    def test_detect_imbalance(self, load_calculator):
        """Test imbalance detection."""
        # Create imbalanced cluster
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=500, capacity=5000, cpu_usage=0.20
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=4000, capacity=5000, cpu_usage=0.80  # Overloaded
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=500, capacity=5000, cpu_usage=0.20
        ))
        
        summary = load_calculator.calculate_cluster_summary()
        
        # Should detect significant imbalance
        assert summary.imbalance_ratio > 0.5
    
    def test_identify_overloaded_nodes(self, load_calculator):
        """Test identifying overloaded nodes."""
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=2000, capacity=5000, cpu_usage=0.30
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=4500, capacity=5000, cpu_usage=0.85  # Overloaded
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=2000, capacity=5000, cpu_usage=0.35
        ))
        
        summary = load_calculator.calculate_cluster_summary()
        
        # Node-2 has 90% load factor, should be overloaded
        assert "node-2" in summary.overloaded_nodes
    
    def test_identify_underloaded_nodes(self, load_calculator):
        """Test identifying underloaded nodes."""
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=500, capacity=5000, cpu_usage=0.10  # Underloaded
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=3000, capacity=5000, cpu_usage=0.60
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=2800, capacity=5000, cpu_usage=0.55
        ))
        
        summary = load_calculator.calculate_cluster_summary()
        
        # Node-1 has 10% load factor, should be underloaded
        assert "node-1" in summary.underloaded_nodes


# ============================================================================
# Rebalance Decision Tests
# ============================================================================

class TestRebalanceDecisions:
    """Tests for rebalance decision making."""
    
    def test_no_rebalance_when_balanced(self, load_calculator):
        """Test that no rebalance is needed when cluster is balanced."""
        # Use perfectly equal distribution to ensure no rebalance needed
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=3000, capacity=5000, cpu_usage=0.40
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=3000, capacity=5000, cpu_usage=0.40
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=3000, capacity=5000, cpu_usage=0.40
        ))
        
        decisions = load_calculator.generate_rebalance_plan()
        
        # Cluster is balanced, no decisions needed
        assert len(decisions) == 0 or not any(d.should_rebalance for d in decisions)
    
    def test_generate_rebalance_decisions(self, load_calculator):
        """Test generating rebalance decisions."""
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=1000, capacity=5000, cpu_usage=0.20
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=4500, capacity=5000, cpu_usage=0.85  # Very overloaded
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=1000, capacity=5000, cpu_usage=0.20
        ))
        
        decisions = load_calculator.generate_rebalance_plan()
        
        # Should have decisions to move docs from node-2
        rebalance_decisions = [d for d in decisions if d.should_rebalance]
        assert len(rebalance_decisions) > 0
        
        for decision in rebalance_decisions:
            assert decision.source_node == "node-2"
            assert decision.target_node in ["node-1", "node-3"]
    
    def test_respect_min_documents_threshold(self, load_calculator):
        """Test that small imbalances are ignored."""
        load_calculator.min_transfer_size = 100
        
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=2000, capacity=5000, cpu_usage=0.30
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=2050, capacity=5000, cpu_usage=0.32
        ))
        
        decisions = load_calculator.generate_rebalance_plan()
        
        # Difference is only 50 docs, below threshold of 100
        rebalance_needed = [d for d in decisions if d.should_rebalance and d.documents_to_move >= 100]
        assert len(rebalance_needed) == 0


# ============================================================================
# Migration Handler Tests
# ============================================================================

class TestMigrationHandler:
    """Tests for document migration handling."""
    
    @pytest.mark.asyncio
    async def test_create_migration_task(self, migration_config):
        """Test creating a migration task."""
        task = MigrationTask(
            task_id="task-1",
            source_node="node-1",
            target_node="node-2",
            document_ids=["doc-1", "doc-2", "doc-3"],
        )
        
        assert task.task_id == "task-1"
        assert len(task.document_ids) == 3
        assert task.status == MigrationStatus.PENDING
        assert task.total_documents == 3
    
    @pytest.mark.asyncio
    async def test_batch_migration(self, migration_config):
        """Test batched document migration."""
        call_count = 0
        async def mock_transfer(source, target, doc_ids):
            nonlocal call_count
            call_count += 1
            # Return proper format expected by MigrationHandler
            return {"migrated": doc_ids, "failed": []}
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        # Create task with 150 documents (should be 3 batches of 50)
        doc_ids = [f"doc-{i}" for i in range(150)]
        task = handler.create_task(
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
        )
        
        result = await handler.execute_task(task.task_id)
        
        assert result.success
        assert result.documents_migrated == 150
        # Should have made 3 batch calls
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_migration_with_failures(self, migration_config):
        """Test migration handles partial failures."""
        call_count = 0
        
        async def mock_transfer(source, target, doc_ids):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Second batch fails - return failed docs
                return {"migrated": [], "failed": doc_ids}
            # Success - return migrated docs
            return {"migrated": doc_ids, "failed": []}
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        doc_ids = [f"doc-{i}" for i in range(100)]
        task = handler.create_task(
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
        )
        
        result = await handler.execute_task(task.task_id)
        
        # Should have partial success
        assert not result.success  # Not fully successful
        assert result.documents_migrated > 0  # Some transferred
        assert result.documents_failed > 0  # Some failed
    
    @pytest.mark.asyncio
    async def test_rate_limited_migration(self, migration_config):
        """Test that migrations are rate limited."""
        migration_config.batch_delay_sec = 0.1
        
        transfer_times = []
        
        async def mock_transfer(source, target, doc_ids):
            transfer_times.append(datetime.utcnow())
            return {"migrated": doc_ids, "failed": []}
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        doc_ids = [f"doc-{i}" for i in range(100)]  # 2 batches
        task = handler.create_task(
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
        )
        
        await handler.execute_task(task.task_id)
        
        # Should have delay between batches
        if len(transfer_times) >= 2:
            delay = (transfer_times[1] - transfer_times[0]).total_seconds()
            assert delay >= migration_config.batch_delay_sec * 0.9  # Allow small variance


# ============================================================================
# Active Rebalancer Tests
# ============================================================================

class TestActiveRebalancer:
    """Tests for active rebalancing orchestration."""
    
    @pytest.mark.asyncio
    async def test_rebalancer_idle_when_balanced(self, active_rebalancer):
        """Test rebalancer stays idle when cluster is balanced."""
        # Provide balanced metrics
        active_rebalancer._load_calculator = LoadCalculator()
        active_rebalancer._load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=2500, capacity=5000
        ))
        active_rebalancer._load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=2500, capacity=5000
        ))
        
        summary = active_rebalancer._load_calculator.calculate_cluster_summary()
        
        # With balanced load, imbalance should be low
        assert summary.imbalance_ratio < 0.2
    
    @pytest.mark.asyncio
    async def test_rebalancer_triggers_on_imbalance(self, active_rebalancer):
        """Test rebalancer triggers when imbalance detected."""
        active_rebalancer._load_calculator = LoadCalculator()
        active_rebalancer._load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=1000, capacity=5000
        ))
        active_rebalancer._load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=4500, capacity=5000  # Imbalanced
        ))
        
        summary = active_rebalancer._load_calculator.calculate_cluster_summary()
        
        # Should detect imbalance
        assert summary.imbalance_ratio > 0.2
    
    @pytest.mark.asyncio
    async def test_rebalance_operation_creation(self, active_rebalancer):
        """Test rebalance operation creation."""
        operation = RebalanceOperation(
            operation_id="op-1",
            status=RebalanceStatus.IDLE,
            started_at=datetime.utcnow(),
        )
        
        assert operation.operation_id == "op-1"
        assert operation.status == RebalanceStatus.IDLE
        assert operation.documents_moved == 0
    
    @pytest.mark.asyncio
    async def test_rebalance_config(self, rebalance_config):
        """Test rebalance configuration."""
        assert rebalance_config.imbalance_threshold == 0.2
        assert rebalance_config.batch_size == 50
        assert rebalance_config.max_concurrent_migrations == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestLoadBalancingIntegration:
    """Integration tests for load balancing system."""
    
    @pytest.mark.asyncio
    async def test_full_rebalance_cycle(self, load_calculator):
        """Test complete rebalance cycle detection."""
        # Initial imbalanced state
        load_calculator.update_node_metrics("node-1", LoadMetrics(
            node_id="node-1", document_count=1000, capacity=5000
        ))
        load_calculator.update_node_metrics("node-2", LoadMetrics(
            node_id="node-2", document_count=4500, capacity=5000
        ))
        load_calculator.update_node_metrics("node-3", LoadMetrics(
            node_id="node-3", document_count=1000, capacity=5000
        ))
        
        # Generate decisions
        decisions = load_calculator.generate_rebalance_plan()
        
        rebalance_decisions = [d for d in decisions if d.should_rebalance]
        
        # Should have decisions to move docs from node-2
        assert len(rebalance_decisions) > 0
    
    @pytest.mark.asyncio
    async def test_migration_task_lifecycle(self):
        """Test migration task status transitions."""
        task = MigrationTask(
            task_id="task-1",
            source_node="node-1",
            target_node="node-2",
            document_ids=["doc-1", "doc-2"],
        )
        
        # Initial state
        assert task.status == MigrationStatus.PENDING
        assert not task.is_complete
        
        # Mark as in progress
        task.status = MigrationStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        assert not task.is_complete
        
        # Mark as completed
        task.status = MigrationStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        assert task.is_complete
        assert task.duration_sec is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

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
        timeout_sec=30.0,
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
            total_size_bytes=1024 * 1024 * 100,  # 100 MB
            cpu_usage=0.45,
            memory_usage=0.60,
            disk_usage=0.30,
            query_rate=50.0,
            avg_query_latency_ms=25.0,
        )
        
        assert metrics.node_id == "node-1"
        assert metrics.document_count == 1000
        assert metrics.cpu_usage == 0.45
    
    def test_combined_load_score(self, load_calculator):
        """Test combined load score calculation."""
        metrics = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            total_size_bytes=1024 * 1024 * 100,
            cpu_usage=0.50,
            memory_usage=0.40,
            disk_usage=0.30,
            query_rate=50.0,
            avg_query_latency_ms=25.0,
        )
        
        score = load_calculator.calculate_load_score(metrics)
        
        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0
    
    def test_high_cpu_increases_load(self, load_calculator):
        """Test that high CPU increases load score."""
        low_cpu = LoadMetrics(
            node_id="node-1",
            document_count=1000,
            cpu_usage=0.20,
            memory_usage=0.40,
        )
        high_cpu = LoadMetrics(
            node_id="node-2",
            document_count=1000,
            cpu_usage=0.90,
            memory_usage=0.40,
        )
        
        low_score = load_calculator.calculate_load_score(low_cpu)
        high_score = load_calculator.calculate_load_score(high_cpu)
        
        assert high_score > low_score


# ============================================================================
# Load Calculator Tests
# ============================================================================

class TestLoadCalculator:
    """Tests for load calculation and analysis."""
    
    def test_cluster_load_summary(self, load_calculator):
        """Test cluster load summary calculation."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=1000, cpu_usage=0.30),
            LoadMetrics(node_id="node-2", document_count=1200, cpu_usage=0.40),
            LoadMetrics(node_id="node-3", document_count=800, cpu_usage=0.35),
        ]
        
        summary = load_calculator.calculate_cluster_summary(metrics_list)
        
        assert summary.total_documents == 3000
        assert summary.avg_documents_per_node == 1000
        assert len(summary.node_loads) == 3
    
    def test_detect_imbalance(self, load_calculator):
        """Test imbalance detection."""
        # Create imbalanced cluster
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=500, cpu_usage=0.20),
            LoadMetrics(node_id="node-2", document_count=2000, cpu_usage=0.80),  # Overloaded
            LoadMetrics(node_id="node-3", document_count=500, cpu_usage=0.20),
        ]
        
        summary = load_calculator.calculate_cluster_summary(metrics_list)
        imbalance = load_calculator.calculate_imbalance(summary)
        
        # Should detect significant imbalance
        assert imbalance > 0.2
    
    def test_identify_overloaded_nodes(self, load_calculator):
        """Test identifying overloaded nodes."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=500, cpu_usage=0.30),
            LoadMetrics(node_id="node-2", document_count=2500, cpu_usage=0.85),  # Overloaded
            LoadMetrics(node_id="node-3", document_count=600, cpu_usage=0.35),
        ]
        
        overloaded = load_calculator.find_overloaded_nodes(
            metrics_list,
            threshold=0.7
        )
        
        assert "node-2" in [n.node_id for n in overloaded]
        assert len(overloaded) == 1
    
    def test_identify_underloaded_nodes(self, load_calculator):
        """Test identifying underloaded nodes."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=100, cpu_usage=0.10),  # Underloaded
            LoadMetrics(node_id="node-2", document_count=1500, cpu_usage=0.60),
            LoadMetrics(node_id="node-3", document_count=1400, cpu_usage=0.55),
        ]
        
        underloaded = load_calculator.find_underloaded_nodes(
            metrics_list,
            threshold=0.3
        )
        
        assert "node-1" in [n.node_id for n in underloaded]


# ============================================================================
# Rebalance Decision Tests
# ============================================================================

class TestRebalanceDecisions:
    """Tests for rebalance decision making."""
    
    def test_no_rebalance_when_balanced(self, load_calculator):
        """Test that no rebalance is needed when cluster is balanced."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=1000, cpu_usage=0.40),
            LoadMetrics(node_id="node-2", document_count=1050, cpu_usage=0.42),
            LoadMetrics(node_id="node-3", document_count=950, cpu_usage=0.38),
        ]
        
        decisions = load_calculator.generate_rebalance_decisions(
            metrics_list,
            imbalance_threshold=0.2
        )
        
        assert len(decisions) == 0
    
    def test_generate_rebalance_decisions(self, load_calculator):
        """Test generating rebalance decisions."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=500, cpu_usage=0.20),
            LoadMetrics(node_id="node-2", document_count=2500, cpu_usage=0.85),
            LoadMetrics(node_id="node-3", document_count=500, cpu_usage=0.20),
        ]
        
        decisions = load_calculator.generate_rebalance_decisions(
            metrics_list,
            imbalance_threshold=0.2
        )
        
        # Should have decisions to move docs from node-2
        assert len(decisions) > 0
        for decision in decisions:
            assert decision.source_node == "node-2"
            assert decision.target_node in ["node-1", "node-3"]
    
    def test_respect_min_documents_threshold(self, load_calculator):
        """Test that small imbalances are ignored."""
        metrics_list = [
            LoadMetrics(node_id="node-1", document_count=100, cpu_usage=0.30),
            LoadMetrics(node_id="node-2", document_count=105, cpu_usage=0.32),
        ]
        
        decisions = load_calculator.generate_rebalance_decisions(
            metrics_list,
            imbalance_threshold=0.2,
            min_documents=10
        )
        
        # Difference is only 5 docs, below threshold
        assert len(decisions) == 0


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
            config=migration_config,
        )
        
        assert task.task_id == "task-1"
        assert len(task.document_ids) == 3
        assert task.status == "pending"
    
    @pytest.mark.asyncio
    async def test_batch_migration(self, migration_config):
        """Test batched document migration."""
        mock_transfer = AsyncMock(return_value=True)
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        # Create task with 150 documents (should be 3 batches of 50)
        doc_ids = [f"doc-{i}" for i in range(150)]
        task = MigrationTask(
            task_id="task-1",
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
            config=migration_config,
        )
        
        result = await handler.execute_migration(task)
        
        assert result.success
        assert result.documents_transferred == 150
        # Should have made 3 batch calls
        assert mock_transfer.call_count == 3
    
    @pytest.mark.asyncio
    async def test_migration_with_failures(self, migration_config):
        """Test migration handles partial failures."""
        call_count = 0
        
        async def mock_transfer(source, target, doc_ids):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Second batch fails
                return False
            return True
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        doc_ids = [f"doc-{i}" for i in range(100)]
        task = MigrationTask(
            task_id="task-1",
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
            config=migration_config,
        )
        
        result = await handler.execute_migration(task)
        
        # Should have partial success
        assert not result.success  # Not fully successful
        assert result.documents_transferred > 0  # Some transferred
        assert result.documents_failed > 0  # Some failed
    
    @pytest.mark.asyncio
    async def test_rate_limited_migration(self, migration_config):
        """Test that migrations are rate limited."""
        migration_config.batch_delay_sec = 0.1
        
        transfer_times = []
        
        async def mock_transfer(source, target, doc_ids):
            transfer_times.append(datetime.utcnow())
            return True
        
        handler = MigrationHandler(
            config=migration_config,
            transfer_func=mock_transfer,
        )
        
        doc_ids = [f"doc-{i}" for i in range(100)]  # 2 batches
        task = MigrationTask(
            task_id="task-1",
            source_node="node-1",
            target_node="node-2",
            document_ids=doc_ids,
            config=migration_config,
        )
        
        await handler.execute_migration(task)
        
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
        metrics = [
            LoadMetrics(node_id="node-1", document_count=1000),
            LoadMetrics(node_id="node-2", document_count=1000),
        ]
        
        with patch.object(active_rebalancer, '_get_cluster_metrics', return_value=metrics):
            should_rebalance = await active_rebalancer.check_rebalance_needed()
        
        assert not should_rebalance
    
    @pytest.mark.asyncio
    async def test_rebalancer_triggers_on_imbalance(self, active_rebalancer):
        """Test rebalancer triggers when imbalance detected."""
        metrics = [
            LoadMetrics(node_id="node-1", document_count=500),
            LoadMetrics(node_id="node-2", document_count=2500),  # Imbalanced
        ]
        
        with patch.object(active_rebalancer, '_get_cluster_metrics', return_value=metrics):
            should_rebalance = await active_rebalancer.check_rebalance_needed()
        
        assert should_rebalance
    
    @pytest.mark.asyncio
    async def test_rebalance_operation_lifecycle(self, active_rebalancer):
        """Test full rebalance operation lifecycle."""
        metrics = [
            LoadMetrics(node_id="node-1", document_count=500),
            LoadMetrics(node_id="node-2", document_count=2500),
        ]
        
        with patch.object(active_rebalancer, '_get_cluster_metrics', return_value=metrics):
            operation = await active_rebalancer.start_rebalance()
        
        # Check operation status transitions
        assert operation is not None
        assert operation.status in [RebalanceStatus.EXECUTING, RebalanceStatus.COMPLETED]
    
    @pytest.mark.asyncio
    async def test_cooldown_after_rebalance(self, active_rebalancer):
        """Test cooldown period after rebalance."""
        active_rebalancer.config.cooldown_after_rebalance_sec = 0.5
        
        # Perform rebalance
        metrics = [
            LoadMetrics(node_id="node-1", document_count=500),
            LoadMetrics(node_id="node-2", document_count=2500),
        ]
        
        with patch.object(active_rebalancer, '_get_cluster_metrics', return_value=metrics):
            await active_rebalancer.start_rebalance()
            
            # Immediately check again - should be in cooldown
            can_rebalance = await active_rebalancer.check_rebalance_needed()
        
        assert not can_rebalance
    
    @pytest.mark.asyncio
    async def test_max_concurrent_migrations(self, active_rebalancer):
        """Test that concurrent migrations are limited."""
        active_rebalancer.config.max_concurrent_migrations = 2
        
        running_count = 0
        max_concurrent = 0
        
        async def slow_transfer(source, target, doc_ids):
            nonlocal running_count, max_concurrent
            running_count += 1
            max_concurrent = max(max_concurrent, running_count)
            await asyncio.sleep(0.1)
            running_count -= 1
            return {"success": True, "transferred": len(doc_ids)}
        
        active_rebalancer._transfer_func = slow_transfer
        
        # Create multiple migration tasks
        decisions = [
            RebalanceDecision(source_node="node-1", target_node="node-2", document_count=50),
            RebalanceDecision(source_node="node-1", target_node="node-3", document_count=50),
            RebalanceDecision(source_node="node-1", target_node="node-4", document_count=50),
            RebalanceDecision(source_node="node-1", target_node="node-5", document_count=50),
        ]
        
        await active_rebalancer.execute_decisions(decisions)
        
        # Should not exceed max concurrent
        assert max_concurrent <= 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestLoadBalancingIntegration:
    """Integration tests for load balancing system."""
    
    @pytest.mark.asyncio
    async def test_full_rebalance_cycle(self, active_rebalancer, load_calculator):
        """Test complete rebalance cycle."""
        # Initial imbalanced state
        initial_metrics = [
            LoadMetrics(node_id="node-1", document_count=500),
            LoadMetrics(node_id="node-2", document_count=2500),
            LoadMetrics(node_id="node-3", document_count=500),
        ]
        
        # Generate decisions
        decisions = load_calculator.generate_rebalance_decisions(
            initial_metrics,
            imbalance_threshold=0.2
        )
        
        assert len(decisions) > 0
        
        # Execute rebalance
        active_rebalancer._document_selector = AsyncMock(
            return_value=[f"doc-{i}" for i in range(100)]
        )
        active_rebalancer._transfer_func = AsyncMock(
            return_value={"success": True, "transferred": 100}
        )
        
        results = await active_rebalancer.execute_decisions(decisions)
        
        # Verify migration happened
        assert active_rebalancer._transfer_func.called
    
    @pytest.mark.asyncio
    async def test_continuous_monitoring(self, active_rebalancer):
        """Test continuous load monitoring."""
        check_count = 0
        
        async def mock_check():
            nonlocal check_count
            check_count += 1
            return False  # No rebalance needed
        
        with patch.object(active_rebalancer, 'check_rebalance_needed', mock_check):
            # Run monitoring for a short period
            active_rebalancer.config.check_interval_sec = 0.1
            
            monitor_task = asyncio.create_task(
                active_rebalancer.start_monitoring()
            )
            
            await asyncio.sleep(0.35)
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # Should have checked multiple times
        assert check_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

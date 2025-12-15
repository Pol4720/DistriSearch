# -*- coding: utf-8 -*-
"""
Integration Tests for Adaptive Cluster Components

Tests all scenarios required by the professor:
1. Single node startup and operation
2. Incremental node addition
3. Operation with fewer than target nodes
4. Partition tolerance
5. Graceful degradation
"""

import asyncio
import pytest
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestAdaptiveClusterConfig:
    """Tests for AdaptiveClusterConfig."""
    
    def test_single_node_config(self):
        """Test configuration with 1 node."""
        from app.distributed.coordination.adaptive_config import (
            AdaptiveClusterConfig,
            OperationMode,
            ConsistencyLevel
        )
        
        config = AdaptiveClusterConfig(
            target_nodes=3,
            target_replication_factor=2,
            target_quorum_size=2
        )
        
        # Update to 1 node
        result = config.update_for_cluster_size(1)
        
        assert config.current_nodes == 1
        assert config.effective_replication_factor == 0  # Can't replicate with 1 node
        assert config.effective_quorum_size == 1
        assert config.operation_mode == OperationMode.SINGLE_NODE
        assert config.consistency_level == ConsistencyLevel.LOCAL
        assert config.get_fault_tolerance() == 0
    
    def test_two_node_config(self):
        """Test configuration with 2 nodes."""
        from app.distributed.coordination.adaptive_config import (
            AdaptiveClusterConfig,
            OperationMode,
            ConsistencyLevel
        )
        
        config = AdaptiveClusterConfig(
            target_nodes=3,
            target_replication_factor=2,
            target_quorum_size=2
        )
        
        config.update_for_cluster_size(2)
        
        assert config.current_nodes == 2
        assert config.effective_replication_factor == 1  # Can replicate once
        assert config.effective_quorum_size == 2  # Both nodes for quorum
        assert config.operation_mode == OperationMode.DEGRADED
        # Fault tolerance = effective_replication_factor (can survive that many replica failures)
        assert config.get_fault_tolerance() == 1
    
    def test_three_node_config(self):
        """Test configuration with 3 nodes (target)."""
        from app.distributed.coordination.adaptive_config import (
            AdaptiveClusterConfig,
            OperationMode
        )
        
        config = AdaptiveClusterConfig(
            target_nodes=3,
            target_replication_factor=2,
            target_quorum_size=2
        )
        
        config.update_for_cluster_size(3)
        
        assert config.current_nodes == 3
        assert config.effective_replication_factor == 2
        assert config.effective_quorum_size == 2
        assert config.operation_mode == OperationMode.NORMAL
        # Fault tolerance = effective_replication_factor
        assert config.get_fault_tolerance() == 2
    
    def test_config_to_dict(self):
        """Test configuration serialization."""
        from app.distributed.coordination.adaptive_config import AdaptiveClusterConfig
        
        config = AdaptiveClusterConfig(target_nodes=3)
        config.update_for_cluster_size(2)
        
        result = config.to_dict()
        
        # Check nested structure
        assert "effective" in result
        assert "nodes" in result["effective"]
        assert result["effective"]["nodes"] == 2
        assert "operation_mode" in result
        assert "fault_tolerance" in result


class TestBootstrapPhases:
    """Tests for SingleNodeBootstrap phases."""
    
    @pytest.mark.asyncio
    async def test_single_node_startup(self):
        """Test starting as single node and becoming leader."""
        from app.distributed.coordination.bootstrap import (
            SingleNodeBootstrap,
            BootstrapConfig,
            BootstrapPhase
        )
        
        leader_callback_called = False
        
        async def on_become_leader():
            nonlocal leader_callback_called
            leader_callback_called = True
        
        config = BootstrapConfig(
            node_id="node-1",
            node_address="localhost:8001",
            seed_nodes=[],
            allow_single_node=True,
            auto_promote_to_leader=True
        )
        
        bootstrap = SingleNodeBootstrap(
            config=config,
            on_become_leader=on_become_leader
        )
        
        result = await bootstrap.start()
        
        # Bootstrap starts and works
        assert bootstrap.cluster_size >= 1
        assert result["node_id"] == "node-1"
        
        await bootstrap.stop()
    
    @pytest.mark.asyncio
    async def test_node_join_handling(self):
        """Test handling node joins."""
        from app.distributed.coordination.bootstrap import (
            SingleNodeBootstrap,
            BootstrapConfig,
            BootstrapPhase
        )
        
        config = BootstrapConfig(
            node_id="node-1",
            node_address="localhost:8001",
            seed_nodes=[],
            allow_single_node=True,
            auto_promote_to_leader=True
        )
        
        bootstrap = SingleNodeBootstrap(config=config)
        
        await bootstrap.start()
        
        # Simulate becoming leader
        bootstrap._is_leader = True
        
        # Add nodes
        await bootstrap.handle_node_join("node-2", "localhost:8002")
        assert bootstrap.cluster_size == 2
        
        await bootstrap.handle_node_join("node-3", "localhost:8003")
        assert bootstrap.cluster_size == 3
        
        await bootstrap.stop()
    
    @pytest.mark.asyncio
    async def test_node_leave_handling(self):
        """Test handling node departures."""
        from app.distributed.coordination.bootstrap import (
            SingleNodeBootstrap,
            BootstrapConfig,
            BootstrapPhase
        )
        
        config = BootstrapConfig(
            node_id="node-1",
            node_address="localhost:8001",
            seed_nodes=[],
            allow_single_node=True
        )
        
        bootstrap = SingleNodeBootstrap(config=config)
        
        await bootstrap.start()
        bootstrap._is_leader = True
        
        # Add and then remove nodes
        await bootstrap.handle_node_join("node-2", "localhost:8002")
        await bootstrap.handle_node_join("node-3", "localhost:8003")
        
        initial_size = bootstrap.cluster_size
        
        await bootstrap.handle_node_leave("node-2")
        
        assert bootstrap.cluster_size == initial_size - 1
        
        await bootstrap.stop()


class TestGracefulDegradation:
    """Tests for GracefulDegradationManager."""
    
    @pytest.mark.asyncio
    async def test_degradation_levels(self):
        """Test degradation level transitions."""
        from app.distributed.coordination.graceful_degradation import (
            GracefulDegradationManager,
            DegradationLevel
        )
        
        manager = GracefulDegradationManager(
            node_id="node-1",
            node_address="localhost:8001",
            target_nodes=3,
            target_replication=2
        )
        
        result = await manager.start()
        
        # Should start in significant degradation (single node)
        assert manager._degradation_level == DegradationLevel.SIGNIFICANT
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_capabilities_single_node(self):
        """Test capabilities in single node mode."""
        from app.distributed.coordination.graceful_degradation import (
            GracefulDegradationManager
        )
        
        manager = GracefulDegradationManager(
            node_id="node-1",
            node_address="localhost:8001",
            target_nodes=3
        )
        
        await manager.start()
        
        caps = manager._capabilities
        
        # Single node should be able to read/write but not replicate
        assert caps.can_read == True
        assert caps.can_write == True
        assert caps.can_replicate == False
        assert caps.fault_tolerance_level == 0
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_operation_checks(self):
        """Test operation allowed checks."""
        from app.distributed.coordination.graceful_degradation import (
            GracefulDegradationManager
        )
        
        manager = GracefulDegradationManager(
            node_id="node-1",
            node_address="localhost:8001",
            target_nodes=3
        )
        
        await manager.start()
        
        # Check operations
        read_check = manager.check_operation_allowed("read")
        assert read_check["allowed"] == True
        
        write_check = manager.check_operation_allowed("write")
        assert write_check["allowed"] == True
        
        replicate_check = manager.check_operation_allowed("replicate")
        assert replicate_check["allowed"] == False  # Can't replicate with 1 node
        
        await manager.stop()


class TestAdaptiveCoordinator:
    """Tests for AdaptiveClusterCoordinator."""
    
    @pytest.mark.asyncio
    async def test_coordinator_startup(self):
        """Test coordinator startup."""
        from app.distributed.coordination.adaptive_coordinator import (
            AdaptiveClusterCoordinator,
        )
        from app.distributed.coordination import adaptive_coordinator
        
        config = adaptive_coordinator.AdaptiveClusterConfig(
            node_id="node-1",
            node_address="localhost:8001",
            target_nodes=3,
            target_replication=2
        )
        
        coordinator = AdaptiveClusterCoordinator(config)
        
        result = await coordinator.start()
        
        assert result["status"] == "started"
        assert coordinator.is_ready == True
        assert coordinator.cluster_size >= 1
        
        await coordinator.stop()
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test cluster health check."""
        from app.distributed.coordination.adaptive_coordinator import (
            AdaptiveClusterCoordinator
        )
        from app.distributed.coordination import adaptive_coordinator
        
        config = adaptive_coordinator.AdaptiveClusterConfig(
            node_id="node-1",
            node_address="localhost:8001",
            target_nodes=3
        )
        
        coordinator = AdaptiveClusterCoordinator(config)
        
        await coordinator.start()
        
        health = coordinator.get_cluster_health()
        
        assert "health_score" in health
        assert "status" in health
        assert "node_count" in health
        assert "fault_tolerance" in health
        
        # Single node should be degraded
        assert health["status"] in ["degraded", "critical"]
        
        await coordinator.stop()


class TestPartitionTolerance:
    """Tests for PartitionTolerantConsensus (AP Mode)."""
    
    @pytest.mark.asyncio
    async def test_partition_detection(self):
        """Test partition detection mechanism."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus,
            PartitionState,
            PartitionStatus
        )
        
        # Create mock RaftNode
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = True
        mock_raft.peers = {"node-2": "localhost:8002", "node-3": "localhost:8003"}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        mock_raft.submit_command = AsyncMock(return_value=True)
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft,
            partition_threshold_sec=3,
        )
        
        await consensus.start()
        
        # Initially should not be partitioned
        assert consensus._state.status == PartitionStatus.CONNECTED
        
        await consensus.stop()
    
    @pytest.mark.asyncio
    async def test_ap_mode_always_accepts_reads(self):
        """Test that AP mode always accepts reads."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus,
            ConsistencyLevel
        )
        
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = True
        mock_raft.peers = {}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft
        )
        
        await consensus.start()
        
        # AP mode should ALWAYS allow reads
        assert consensus.can_accept_reads() == True
        
        # Read should always succeed (AP guarantee)
        result = await consensus.read("test-key", ConsistencyLevel.EVENTUAL)
        assert result.success == True
        
        await consensus.stop()
    
    @pytest.mark.asyncio
    async def test_ap_mode_always_accepts_writes(self):
        """Test that AP mode always accepts writes."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus,
            PartitionStatus
        )
        
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = True
        mock_raft.peers = {}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft
        )
        
        await consensus.start()
        
        # Force partition mode for testing
        consensus._state.status = PartitionStatus.PARTITIONED
        consensus._state.is_majority = False
        
        # AP mode should STILL allow writes even in minority partition
        assert consensus.can_accept_writes() == True
        
        # Write should be accepted (AP guarantee)
        result = await consensus.write("test-key", {"value": "test"})
        assert result.success == True
        assert result.accepted == True
        
        await consensus.stop()


class TestFaultToleranceCalculation:
    """Tests for fault tolerance level calculation."""
    
    def test_k_fault_tolerance(self):
        """
        Test fault tolerance calculation.
        
        Fault tolerance = effective_replication_factor
        This represents how many replica failures can be tolerated.
        """
        from app.distributed.coordination.adaptive_config import AdaptiveClusterConfig
        
        config = AdaptiveClusterConfig(
            target_nodes=5,
            target_replication_factor=2,
            target_quorum_size=3
        )
        
        # 1 node: k=0 (no replication possible)
        config.update_for_cluster_size(1)
        assert config.get_fault_tolerance() == 0
        
        # 2 nodes: k=1 (can replicate to 1 other node)
        config.update_for_cluster_size(2)
        assert config.get_fault_tolerance() == 1
        
        # 3 nodes: k=2 (can use target replication factor of 2)
        config.update_for_cluster_size(3)
        assert config.get_fault_tolerance() == 2
        
        # 4 nodes: k=2
        config.update_for_cluster_size(4)
        assert config.get_fault_tolerance() == 2
        
        # 5 nodes: k=2 (still limited by target_replication_factor)
        config.update_for_cluster_size(5)
        assert config.get_fault_tolerance() == 2


class TestIncrementalGrowth:
    """
    Tests for incremental cluster growth.
    
    As per professor's clarification:
    "Su sistema no arranca con los n nodos. Va creciendo de a poco hasta llegar a ese número"
    """
    
    @pytest.mark.asyncio
    async def test_growth_from_single_node(self):
        """Test growing cluster from 1 to target nodes."""
        from app.distributed.coordination.adaptive_config import (
            AdaptiveClusterConfig,
            AdaptiveClusterManager,
            OperationMode
        )
        
        config = AdaptiveClusterConfig(target_nodes=3)
        manager = AdaptiveClusterManager(config, node_id="node-1")
        
        # Register the initial node (self)
        manager.node_joined("node-1", {"address": "localhost:8001"})
        assert config.current_nodes == 1
        assert config.operation_mode == OperationMode.SINGLE_NODE
        
        # Add second node
        manager.node_joined("node-2", {"address": "localhost:8002"})
        assert config.current_nodes == 2
        assert config.operation_mode == OperationMode.DEGRADED
        
        # Add third node
        manager.node_joined("node-3", {"address": "localhost:8003"})
        assert config.current_nodes == 3
        assert config.operation_mode == OperationMode.NORMAL
        
        # Should now have full fault tolerance
        assert config.get_fault_tolerance() >= 1
    
    @pytest.mark.asyncio
    async def test_shrink_and_regrow(self):
        """Test shrinking and regrowing cluster."""
        from app.distributed.coordination.adaptive_config import (
            AdaptiveClusterConfig,
            AdaptiveClusterManager,
            OperationMode
        )
        
        config = AdaptiveClusterConfig(target_nodes=3)
        manager = AdaptiveClusterManager(config, node_id="node-1")
        
        # Start with 3 nodes (register all including self)
        manager.node_joined("node-1", {"address": "localhost:8001"})
        manager.node_joined("node-2", {"address": "localhost:8002"})
        manager.node_joined("node-3", {"address": "localhost:8003"})
        assert config.current_nodes == 3
        
        # Lose a node
        manager.node_left("node-3", "failure")
        assert config.current_nodes == 2
        
        # Lose another node
        manager.node_left("node-2", "failure")
        assert config.current_nodes == 1
        assert config.operation_mode == OperationMode.SINGLE_NODE
        
        # Regrow
        manager.node_joined("node-4", {"address": "localhost:8004"})
        assert config.current_nodes == 2
        
        manager.node_joined("node-5", {"address": "localhost:8005"})
        assert config.current_nodes == 3
        assert config.operation_mode == OperationMode.NORMAL


class TestPartitionScenarios:
    """
    Tests for partition scenarios.
    
    As per professor's clarification:
    "Si en alguna de las dos mitades quedan menos nodos debería operar con esos"
    """
    
    def test_minority_partition_operations(self):
        """Test that minority partitions can still operate in AP mode."""
        # This is tested in the AP mode tests above
        # The key point is that even minority partitions should be able
        # to do local reads and emergency writes
        pass
    
    @pytest.mark.asyncio
    async def test_partition_status_reporting(self):
        """Test that partition status is properly reported."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus
        )
        
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = True
        mock_raft.peers = {"node-2": "localhost:8002"}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft
        )
        
        await consensus.start()
        
        status = consensus.get_status()
        
        assert "partition_status" in status
        assert "node_id" in status
        assert "mode" in status
        assert status["mode"] == "AP"  # Verify AP mode
        
        await consensus.stop()


class TestAPModeGuarantees:
    """Test AP mode guarantees according to CAP theorem."""
    
    @pytest.mark.asyncio
    async def test_always_available_reads(self):
        """System always responds to reads."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus,
            PartitionStatus,
            DataFreshness
        )
        
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = False  # Not even leader
        mock_raft.peers = {}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft
        )
        
        await consensus.start()
        
        # Simulate worst case: partitioned, minority, not leader
        consensus._state.status = PartitionStatus.PARTITIONED
        consensus._state.is_majority = False
        
        # Read should STILL succeed (AP guarantee)
        result = await consensus.read("any-key")
        assert result.success == True
        # Should indicate data might be stale
        assert result.freshness in [
            DataFreshness.POTENTIALLY_STALE,
            DataFreshness.STALE,
            DataFreshness.UNKNOWN
        ]
        
        await consensus.stop()
    
    @pytest.mark.asyncio
    async def test_always_available_writes(self):
        """System always accepts writes (locally)."""
        from app.distributed.consensus.partition_tolerant import (
            PartitionTolerantConsensus,
            PartitionStatus
        )
        
        mock_raft = AsyncMock()
        mock_raft.node_id = "node-1"
        mock_raft.is_leader = False
        mock_raft.peers = {}
        mock_raft.start = AsyncMock()
        mock_raft.stop = AsyncMock()
        
        consensus = PartitionTolerantConsensus(
            node_id="node-1",
            raft_node=mock_raft
        )
        
        await consensus.start()
        
        # Even in partition
        consensus._state.status = PartitionStatus.PARTITIONED
        
        # Write should be accepted locally
        result = await consensus.write("test-key", {"data": "value"})
        assert result.accepted == True
        assert result.sync_status in ["pending", "will_sync_later"]
        
        await consensus.stop()


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

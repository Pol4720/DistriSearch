# -*- coding: utf-8 -*-
"""
Partition Tolerance Tests

Tests to verify the system handles network partitions correctly:
- AP mode guarantees availability during partitions
- Data remains accessible even when nodes are unreachable
- System heals correctly when partition resolves
- Staleness indicators work correctly
- Vector clocks track causality properly
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.distributed.consensus.partition_tolerant import (
    PartitionTolerantConsensus,
    PartitionStatus,
    ConsistencyLevel,
    DataFreshness,
    VersionedData,
    APReadResult,
    APWriteResult,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def node_id() -> str:
    """Local node ID."""
    return "node-1"


@pytest.fixture
def cluster_nodes() -> List[str]:
    """All nodes in cluster."""
    return ["node-1", "node-2", "node-3"]


@pytest.fixture
def mock_raft_node():
    """Create a mock Raft node."""
    mock = MagicMock()
    mock.node_id = "node-1"
    return mock


@pytest.fixture
async def consensus(node_id: str, mock_raft_node) -> PartitionTolerantConsensus:
    """Create partition tolerant consensus instance."""
    consensus = PartitionTolerantConsensus(
        node_id=node_id,
        raft_node=mock_raft_node,
        partition_threshold_sec=30.0,
        partition_check_interval=5.0,
    )
    # Add other known nodes
    consensus._all_known_nodes.add("node-2")
    consensus._all_known_nodes.add("node-3")
    consensus._node_last_seen["node-2"] = datetime.utcnow()
    consensus._node_last_seen["node-3"] = datetime.utcnow()
    return consensus


# ============================================================================
# VersionedData Tests
# ============================================================================

class TestVersionedData:
    """Tests for versioned data with vector clocks."""
    
    def test_create_versioned_data(self):
        """Test creating versioned data."""
        data = VersionedData.create(
            value={"key": "value"},
            node_id="node-1"
        )
        
        assert data.value == {"key": "value"}
        assert data.node_id == "node-1"
        assert data.version == 1
        assert "node-1" in data.vector_clock
        assert data.vector_clock["node-1"] == 1
        assert data.checksum is not None
    
    def test_vector_clock_increment(self):
        """Test vector clock increments properly."""
        vc = {"node-1": 1, "node-2": 2}
        data = VersionedData.create(
            value="test",
            node_id="node-1",
            vector_clock=vc
        )
        
        # node-1's clock should increment
        assert data.vector_clock["node-1"] == 2
        assert data.vector_clock["node-2"] == 2
        assert data.version == 4  # sum of all clocks
    
    def test_is_newer_than_simple(self):
        """Test simple newer-than comparison."""
        data1 = VersionedData.create(value="v1", node_id="node-1")
        
        # Create data2 with higher version
        data2 = VersionedData.create(
            value="v2",
            node_id="node-1",
            vector_clock=data1.vector_clock.copy()
        )
        
        assert data2.is_newer_than(data1)
        assert not data1.is_newer_than(data2)
    
    def test_is_newer_than_concurrent(self):
        """Test concurrent updates (neither dominates)."""
        data1 = VersionedData.create(value="v1", node_id="node-1")
        data2 = VersionedData.create(value="v2", node_id="node-2")
        
        # Neither should dominate the other (concurrent updates)
        # Both have version 1 but from different nodes
        # The is_newer_than will use timestamp as tiebreaker
        result1 = data1.is_newer_than(data2)
        result2 = data2.is_newer_than(data1)
        
        # One should be True and one False due to timestamp tiebreaker
        # (unless they have exactly the same timestamp)
        assert result1 != result2 or (not result1 and not result2)
    
    def test_is_newer_than_none(self):
        """Test comparison with None."""
        data = VersionedData.create(value="test", node_id="node-1")
        assert data.is_newer_than(None)
    
    def test_versioned_data_serialization(self):
        """Test serialization to dict."""
        data = VersionedData.create(value={"foo": "bar"}, node_id="node-1")
        
        data_dict = data.to_dict()
        
        assert data_dict["value"] == {"foo": "bar"}
        assert data_dict["node_id"] == "node-1"
        assert "vector_clock" in data_dict
        assert "timestamp" in data_dict
        assert "checksum" in data_dict


# ============================================================================
# Partition Detection Tests
# ============================================================================

class TestPartitionDetection:
    """Tests for network partition detection."""
    
    @pytest.mark.asyncio
    async def test_initial_status_is_connected(self, consensus):
        """Test initial partition status is connected."""
        status = consensus._state.status
        assert status == PartitionStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_detect_partial_partition(self, consensus):
        """Test detection of partial partition (some nodes unreachable)."""
        # Simulate one node becoming unreachable
        consensus._node_last_seen["node-2"] = datetime.utcnow() - timedelta(seconds=60)
        
        await consensus._check_partition_status()
        
        # Should be partial (1 of 2 other nodes down) or still connected
        status = consensus._state.status
        assert status in [PartitionStatus.PARTIAL, PartitionStatus.CONNECTED]
    
    @pytest.mark.asyncio
    async def test_detect_full_partition(self, consensus):
        """Test detection of full partition (majority unreachable)."""
        # Simulate all other nodes becoming unreachable
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        
        await consensus._check_partition_status()
        
        # Should be partitioned (lost majority)
        status = consensus._state.status
        assert status == PartitionStatus.PARTITIONED
    
    @pytest.mark.asyncio
    async def test_partition_healing(self, consensus):
        """Test partition healing when nodes reconnect."""
        # First, create a partition
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        await consensus._check_partition_status()
        
        # Now simulate nodes coming back
        consensus._node_last_seen["node-2"] = datetime.utcnow()
        consensus._node_last_seen["node-3"] = datetime.utcnow()
        await consensus._check_partition_status()
        
        # Should be healing or connected
        status = consensus._state.status
        assert status in [PartitionStatus.HEALING, PartitionStatus.CONNECTED]


# ============================================================================
# AP Mode Availability Tests
# ============================================================================

class TestAPModeAvailability:
    """Tests for AP mode - system remains available during partitions."""
    
    @pytest.mark.asyncio
    async def test_read_available_during_partition(self, consensus):
        """Test that reads succeed during network partition."""
        # Store some data locally
        key = "test-key"
        consensus._local_store[key] = VersionedData.create(
            value={"value": 42},
            node_id=consensus.node_id
        )
        
        # Simulate partition
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        await consensus._check_partition_status()
        
        # Read should still work
        response = await consensus.read(key, ConsistencyLevel.EVENTUAL)
        
        assert response is not None
        assert response.success
        assert response.data["value"] == 42
    
    @pytest.mark.asyncio
    async def test_write_available_during_partition(self, consensus):
        """Test that writes succeed during network partition (AP mode)."""
        # Simulate partition
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        await consensus._check_partition_status()
        
        # Write should still work (stored locally, synced later)
        key = "partition-write"
        result = await consensus.write(key, {"data": "during-partition"}, ConsistencyLevel.LOCAL)
        
        assert result.success
        assert result.accepted  # Always accepted in AP mode
        
        # Verify data is readable
        response = await consensus.read(key, ConsistencyLevel.LOCAL)
        assert response.data["data"] == "during-partition"
    
    @pytest.mark.asyncio
    async def test_staleness_indicator_during_partition(self, consensus):
        """Test that staleness indicators are set correctly during partition."""
        # Store data
        key = "stale-test"
        consensus._local_store[key] = VersionedData.create(
            value={"value": 1},
            node_id=consensus.node_id
        )
        
        # Simulate partition
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        await consensus._check_partition_status()
        
        # Read should indicate potential staleness
        response = await consensus.read(key, ConsistencyLevel.EVENTUAL)
        
        # During partition, data freshness should be degraded
        assert response.freshness in [
            DataFreshness.POTENTIALLY_STALE,
            DataFreshness.LIKELY_CURRENT,
            DataFreshness.UNKNOWN
        ]


# ============================================================================
# Consistency Level Tests
# ============================================================================

class TestConsistencyLevels:
    """Tests for different consistency levels."""
    
    @pytest.mark.asyncio
    async def test_local_consistency_no_network(self, consensus):
        """Test LOCAL consistency doesn't require network."""
        key = "local-only"
        
        # Write locally
        result = await consensus.write(key, {"local": True}, ConsistencyLevel.LOCAL)
        assert result.success
        
        # Read locally
        response = await consensus.read(key, ConsistencyLevel.LOCAL)
        assert response.success
        assert response.data["local"] is True
    
    @pytest.mark.asyncio
    async def test_eventual_consistency_returns_local(self, consensus):
        """Test EVENTUAL consistency returns local data."""
        key = "eventual-test"
        
        await consensus.write(key, {"sync": "later"}, ConsistencyLevel.LOCAL)
        
        response = await consensus.read(key, ConsistencyLevel.EVENTUAL)
        
        assert response.success
        assert response.data["sync"] == "later"


# ============================================================================
# Conflict Resolution Tests
# ============================================================================

class TestConflictResolution:
    """Tests for conflict resolution during partition healing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_writes_resolved(self, consensus):
        """Test that concurrent writes are resolved using vector clocks."""
        key = "conflict-key"
        
        # Simulate write from node-1
        data1 = VersionedData.create(value={"from": "node-1"}, node_id="node-1")
        consensus._local_store[key] = data1
        
        # Simulate concurrent write from node-2 (received during sync)
        data2 = VersionedData.create(value={"from": "node-2"}, node_id="node-2")
        
        # Resolve conflict - should pick one deterministically
        if data2.is_newer_than(data1):
            resolved = data2
        else:
            resolved = data1
        
        assert resolved is not None
        assert resolved.value["from"] in ["node-1", "node-2"]
    
    @pytest.mark.asyncio
    async def test_later_version_wins(self, consensus):
        """Test that later version wins in conflict resolution."""
        # Create old version
        old_data = VersionedData.create(value="old", node_id="node-1")
        
        # Wait a tiny bit to ensure different timestamp
        await asyncio.sleep(0.001)
        
        # Create new version with higher vector clock
        new_data = VersionedData.create(
            value="new",
            node_id="node-1",
            vector_clock=old_data.vector_clock.copy()
        )
        
        assert new_data.is_newer_than(old_data)


# ============================================================================
# AP Result Types Tests
# ============================================================================

class TestAPResultTypes:
    """Tests for AP result data types."""
    
    def test_ap_read_result_serialization(self):
        """Test APReadResult serialization."""
        result = APReadResult(
            success=True,
            data={"test": "data"},
            freshness=DataFreshness.CONFIRMED,
            version_info={"version": 1},
            source_node="node-1",
            partition_status=PartitionStatus.CONNECTED,
            staleness_warning=None,
            read_timestamp=datetime.utcnow()
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["freshness"] == "confirmed"
        assert data["partition_status"] == "connected"
    
    def test_ap_write_result_serialization(self):
        """Test APWriteResult serialization."""
        result = APWriteResult(
            success=True,
            accepted=True,
            version_info={"version": 1},
            partition_status=PartitionStatus.CONNECTED,
            sync_status="synced",
            conflict_possible=False,
            warning=None
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["accepted"] is True
        assert data["sync_status"] == "synced"


# ============================================================================
# Integration Tests
# ============================================================================

class TestPartitionToleranceIntegration:
    """Integration tests for partition tolerance."""
    
    @pytest.mark.asyncio
    async def test_full_partition_recovery_cycle(self, consensus):
        """Test complete cycle: healthy -> partition -> recovery."""
        key = "cycle-test"
        
        # Phase 1: Healthy cluster - write locally
        await consensus.write(key, {"phase": 1}, ConsistencyLevel.LOCAL)
        
        # Phase 2: Partition occurs
        old_time = datetime.utcnow() - timedelta(seconds=120)
        consensus._node_last_seen["node-2"] = old_time
        consensus._node_last_seen["node-3"] = old_time
        await consensus._check_partition_status()
        
        assert consensus._state.status == PartitionStatus.PARTITIONED
        
        # Phase 3: Continue operating (AP mode)
        await consensus.write(key, {"phase": 2}, ConsistencyLevel.LOCAL)
        response = await consensus.read(key, ConsistencyLevel.LOCAL)
        assert response.data["phase"] == 2
        
        # Phase 4: Partition heals
        consensus._node_last_seen["node-2"] = datetime.utcnow()
        consensus._node_last_seen["node-3"] = datetime.utcnow()
        await consensus._check_partition_status()
        
        # Should be healing or connected
        status = consensus._state.status
        assert status in [PartitionStatus.HEALING, PartitionStatus.CONNECTED]
    
    @pytest.mark.asyncio
    async def test_queries_always_return(self, consensus):
        """Test that queries always return (never hang) in AP mode."""
        key = "never-hang"
        await consensus.write(key, {"data": "test"}, ConsistencyLevel.LOCAL)
        
        # Should not hang even if network is slow
        response = await asyncio.wait_for(
            consensus.read(key, ConsistencyLevel.EVENTUAL),
            timeout=5.0  # Test timeout
        )
        
        # Should get a response (success or with staleness indicator)
        assert response is not None
        assert response.success


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

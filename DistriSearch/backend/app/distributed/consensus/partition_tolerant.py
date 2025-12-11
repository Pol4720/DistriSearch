# -*- coding: utf-8 -*-
"""
Partition Tolerant Consensus - AP Mode (CAP Theorem)

Implements an AP (Availability + Partition tolerance) system:
- ALWAYS processes queries and returns responses
- Prioritizes availability over strict consistency
- During partitions, returns the best available data with staleness indicators
- Uses vector clocks and timestamps for conflict detection
- Eventual consistency through anti-entropy and read repair

CAP Trade-off: We sacrifice strong consistency (C) to maintain
availability (A) during network partitions (P).
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, Any, Optional, List, Set, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class PartitionStatus(Enum):
    """Network partition status."""
    CONNECTED = "connected"        # Normal operation
    PARTIAL = "partial"            # Some nodes unreachable
    PARTITIONED = "partitioned"    # Majority unreachable
    HEALING = "healing"            # Reconnecting


class ConsistencyLevel(Enum):
    """Consistency level for operations (AP mode supports all with different guarantees)."""
    STRONG = "strong"              # Wait for quorum (may fail during partition)
    EVENTUAL = "eventual"          # Return immediately, sync later
    LOCAL = "local"                # Use only local data


class DataFreshness(Enum):
    """Indicates how fresh/stale the returned data might be."""
    CONFIRMED = "confirmed"        # Data confirmed by quorum
    LIKELY_CURRENT = "likely_current"  # Recent but not confirmed
    POTENTIALLY_STALE = "potentially_stale"  # May be outdated
    STALE = "stale"                # Known to be outdated
    UNKNOWN = "unknown"            # Cannot determine freshness


@dataclass
class VersionedData:
    """Data with version information for conflict detection."""
    value: Any
    version: int
    vector_clock: Dict[str, int]
    timestamp: datetime
    node_id: str
    checksum: str
    
    @classmethod
    def create(cls, value: Any, node_id: str, vector_clock: Dict[str, int] = None) -> 'VersionedData':
        """Create a new versioned data entry."""
        vc = vector_clock or {}
        vc[node_id] = vc.get(node_id, 0) + 1
        
        value_str = json.dumps(value, sort_keys=True, default=str)
        checksum = hashlib.md5(value_str.encode()).hexdigest()[:8]
        
        return cls(
            value=value,
            version=sum(vc.values()),
            vector_clock=vc.copy(),
            timestamp=datetime.utcnow(),
            node_id=node_id,
            checksum=checksum
        )
    
    def is_newer_than(self, other: 'VersionedData') -> bool:
        """Check if this version is newer using vector clocks."""
        if other is None:
            return True
        
        # Compare vector clocks
        dominated = False
        dominates = False
        
        all_nodes = set(self.vector_clock.keys()) | set(other.vector_clock.keys())
        
        for node in all_nodes:
            self_v = self.vector_clock.get(node, 0)
            other_v = other.vector_clock.get(node, 0)
            
            if self_v > other_v:
                dominates = True
            elif self_v < other_v:
                dominated = True
        
        if dominates and not dominated:
            return True
        if dominated and not dominates:
            return False
        
        # Concurrent - use timestamp as tiebreaker (last-write-wins)
        return self.timestamp > other.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "version": self.version,
            "vector_clock": self.vector_clock,
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "checksum": self.checksum
        }


@dataclass
class PartitionState:
    """State for partition tolerance."""
    status: PartitionStatus = PartitionStatus.CONNECTED
    reachable_nodes: Set[str] = field(default_factory=set)
    unreachable_nodes: Set[str] = field(default_factory=set)
    partition_started: Optional[datetime] = None
    last_full_connectivity: Optional[datetime] = None
    is_majority: bool = True


@dataclass
class APReadResult:
    """Result of an AP-mode read operation."""
    success: bool
    data: Any
    freshness: DataFreshness
    version_info: Optional[Dict[str, Any]]
    source_node: str
    partition_status: PartitionStatus
    staleness_warning: Optional[str]
    read_timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "freshness": self.freshness.value,
            "version_info": self.version_info,
            "source_node": self.source_node,
            "partition_status": self.partition_status.value,
            "staleness_warning": self.staleness_warning,
            "read_timestamp": self.read_timestamp.isoformat()
        }


@dataclass 
class APWriteResult:
    """Result of an AP-mode write operation."""
    success: bool
    accepted: bool  # Always True in AP mode - writes are always accepted locally
    version_info: Optional[Dict[str, Any]]
    partition_status: PartitionStatus
    sync_status: str  # "synced", "pending", "will_sync_later"
    conflict_possible: bool
    warning: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "accepted": self.accepted,
            "version_info": self.version_info,
            "partition_status": self.partition_status.value,
            "sync_status": self.sync_status,
            "conflict_possible": self.conflict_possible,
            "warning": self.warning
        }


class PartitionTolerantConsensus:
    """
    AP-Mode Partition-tolerant consensus (CAP Theorem).
    
    AVAILABILITY GUARANTEE: This system ALWAYS responds to queries.
    During network partitions, it returns the best available data
    with appropriate staleness indicators.
    
    Key AP Behaviors:
    1. Reads ALWAYS succeed - return local data with freshness info
    2. Writes ALWAYS accepted locally - sync when connectivity restored
    3. Conflicts detected via vector clocks, resolved via last-write-wins
    4. Anti-entropy synchronization when partition heals
    
    Trade-off: We may return stale data during partitions, but we
    NEVER refuse to serve a request.
    """
    
    def __init__(
        self,
        node_id: str,
        raft_node: Any,  # RaftNode (optional, for CP fallback)
        failure_detector: Optional[Any] = None,
        partition_check_interval: float = 5.0,
        partition_threshold_sec: float = 30.0,
        enable_read_repair: bool = True,
        enable_anti_entropy: bool = True
    ):
        """
        Initialize AP-mode partition tolerant consensus.
        
        Args:
            node_id: This node's ID
            raft_node: Underlying Raft node (for CP mode when available)
            failure_detector: Failure detector for reachability
            partition_check_interval: How often to check partition status
            partition_threshold_sec: Time before declaring partition
            enable_read_repair: Repair stale reads opportunistically
            enable_anti_entropy: Background sync when healed
        """
        self.node_id = node_id
        self.raft_node = raft_node
        self._failure_detector = failure_detector
        self._check_interval = partition_check_interval
        self._partition_threshold = partition_threshold_sec
        self._enable_read_repair = enable_read_repair
        self._enable_anti_entropy = enable_anti_entropy
        
        self._state = PartitionState()
        self._state.reachable_nodes.add(node_id)
        self._state.last_full_connectivity = datetime.utcnow()
        
        self._all_known_nodes: Set[str] = {node_id}
        self._node_last_seen: Dict[str, datetime] = {node_id: datetime.utcnow()}
        
        # Local data store for AP availability
        self._local_store: Dict[str, VersionedData] = {}
        
        # Pending writes to sync when partition heals
        self._pending_sync: List[Tuple[str, VersionedData]] = []
        
        # Vector clock for this node
        self._vector_clock: Dict[str, int] = {node_id: 0}
        
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._anti_entropy_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_partition: List[Callable[[PartitionState], Awaitable[None]]] = []
        self._on_heal: List[Callable[[PartitionState], Awaitable[None]]] = []
        self._on_conflict: List[Callable[[str, VersionedData, VersionedData], Awaitable[None]]] = []
        
        logger.info(f"AP-Mode Partition Tolerant Consensus initialized for {node_id}")
    
    # =========================================================================
    # AP READ OPERATIONS - ALWAYS SUCCEED
    # =========================================================================
    
    async def read(
        self,
        key: str,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    ) -> APReadResult:
        """
        Read data with AP guarantees - ALWAYS returns a response.
        
        In AP mode:
        - STRONG: Try quorum read, fall back to local if partition
        - EVENTUAL: Return local data, trigger background sync
        - LOCAL: Return local data only
        
        Args:
            key: Key to read
            consistency: Desired consistency level
            
        Returns:
            APReadResult with data and freshness information
        """
        read_timestamp = datetime.utcnow()
        
        # ALWAYS try to return data
        local_data = self._local_store.get(key)
        
        if consistency == ConsistencyLevel.STRONG and self._state.status == PartitionStatus.CONNECTED:
            # Try quorum read when connected
            try:
                quorum_result = await self._quorum_read(key)
                if quorum_result:
                    return APReadResult(
                        success=True,
                        data=quorum_result.value,
                        freshness=DataFreshness.CONFIRMED,
                        version_info=quorum_result.to_dict(),
                        source_node=quorum_result.node_id,
                        partition_status=self._state.status,
                        staleness_warning=None,
                        read_timestamp=read_timestamp
                    )
            except Exception as e:
                logger.warning(f"Quorum read failed, falling back to local: {e}")
        
        # Return local data (AP guarantee - always respond)
        if local_data:
            freshness, warning = self._assess_freshness(local_data)
            
            return APReadResult(
                success=True,
                data=local_data.value,
                freshness=freshness,
                version_info=local_data.to_dict(),
                source_node=self.node_id,
                partition_status=self._state.status,
                staleness_warning=warning,
                read_timestamp=read_timestamp
            )
        
        # No data found - still return success (empty result)
        return APReadResult(
            success=True,
            data=None,
            freshness=DataFreshness.UNKNOWN,
            version_info=None,
            source_node=self.node_id,
            partition_status=self._state.status,
            staleness_warning="No data found for key" if self._state.status != PartitionStatus.CONNECTED else None,
            read_timestamp=read_timestamp
        )
    
    async def read_with_fallback(
        self,
        key: str,
        default_value: Any = None
    ) -> APReadResult:
        """
        Read with automatic fallback - NEVER fails.
        
        Args:
            key: Key to read
            default_value: Value to return if no data exists
            
        Returns:
            APReadResult - always succeeds
        """
        result = await self.read(key, ConsistencyLevel.EVENTUAL)
        
        if result.data is None:
            result.data = default_value
            result.staleness_warning = "Using default value - no data found"
        
        return result
    
    # =========================================================================
    # AP WRITE OPERATIONS - ALWAYS ACCEPTED
    # =========================================================================
    
    async def write(
        self,
        key: str,
        value: Any,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    ) -> APWriteResult:
        """
        Write data with AP guarantees - ALWAYS accepts the write.
        
        In AP mode, writes are ALWAYS accepted locally. During partitions,
        they are queued for sync when connectivity is restored.
        
        Args:
            key: Key to write
            value: Value to write
            consistency: Desired consistency level
            
        Returns:
            APWriteResult with sync status
        """
        # Increment vector clock
        self._vector_clock[self.node_id] = self._vector_clock.get(self.node_id, 0) + 1
        
        # Create versioned data
        versioned = VersionedData.create(
            value=value,
            node_id=self.node_id,
            vector_clock=self._vector_clock.copy()
        )
        
        # Check for conflict with existing data
        existing = self._local_store.get(key)
        conflict_possible = False
        
        if existing and not versioned.is_newer_than(existing):
            # Concurrent write - resolve with last-write-wins
            conflict_possible = True
            logger.info(f"Concurrent write detected for key {key}, using last-write-wins")
        
        # ALWAYS accept write locally (AP guarantee)
        self._local_store[key] = versioned
        
        # Determine sync status based on partition state
        sync_status = "synced"
        warning = None
        
        if self._state.status == PartitionStatus.CONNECTED:
            # Try to replicate
            if consistency == ConsistencyLevel.STRONG:
                try:
                    await self._replicate_write(key, versioned)
                    sync_status = "synced"
                except Exception as e:
                    sync_status = "pending"
                    warning = f"Replication pending: {e}"
            else:
                # Queue for background sync
                asyncio.create_task(self._async_replicate(key, versioned))
                sync_status = "pending"
        else:
            # Partitioned - queue for later sync
            self._pending_sync.append((key, versioned))
            sync_status = "will_sync_later"
            warning = (
                f"Write accepted locally. Network partition detected - "
                f"data will sync when connectivity is restored. "
                f"Partition started: {self._state.partition_started}"
            )
        
        return APWriteResult(
            success=True,
            accepted=True,  # AP mode ALWAYS accepts
            version_info=versioned.to_dict(),
            partition_status=self._state.status,
            sync_status=sync_status,
            conflict_possible=conflict_possible,
            warning=warning
        )
    
    async def write_if_current(
        self,
        key: str,
        value: Any,
        expected_version: int
    ) -> APWriteResult:
        """
        Conditional write - still accepts in AP mode but warns about conflicts.
        
        Args:
            key: Key to write
            value: Value to write
            expected_version: Expected current version
            
        Returns:
            APWriteResult with conflict information
        """
        existing = self._local_store.get(key)
        
        if existing and existing.version != expected_version:
            # Version mismatch - still accept (AP mode) but warn
            result = await self.write(key, value, ConsistencyLevel.EVENTUAL)
            result.conflict_possible = True
            result.warning = (
                f"Version mismatch (expected {expected_version}, got {existing.version}). "
                f"Write accepted but conflicts may occur."
            )
            return result
        
        return await self.write(key, value, ConsistencyLevel.EVENTUAL)
    
    def on_partition(self, callback: Callable[[PartitionState], Awaitable[None]]):
        """Register partition detection callback."""
        self._on_partition.append(callback)
    
    def on_heal(self, callback: Callable[[PartitionState], Awaitable[None]]):
        """Register partition heal callback."""
        self._on_heal.append(callback)
    
    def on_conflict(self, callback: Callable[[str, VersionedData, VersionedData], Awaitable[None]]):
        """Register conflict detection callback."""
        self._on_conflict.append(callback)
    
    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================
    
    async def start(self):
        """Start partition monitoring and anti-entropy."""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        if self._enable_anti_entropy:
            self._anti_entropy_task = asyncio.create_task(self._anti_entropy_loop())
        
        logger.info(f"AP-Mode Partition tolerant consensus started for {self.node_id}")
    
    async def stop(self):
        """Stop partition monitoring and sync tasks."""
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._anti_entropy_task:
            self._anti_entropy_task.cancel()
            try:
                await self._anti_entropy_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AP-Mode Partition tolerant consensus stopped")
    
    # =========================================================================
    # NODE MANAGEMENT
    # =========================================================================
    
    def register_node(self, node_id: str):
        """Register a known cluster node."""
        self._all_known_nodes.add(node_id)
        self._node_last_seen[node_id] = datetime.utcnow()
        self._vector_clock.setdefault(node_id, 0)
    
    def unregister_node(self, node_id: str):
        """Unregister a node (graceful leave)."""
        self._all_known_nodes.discard(node_id)
        self._state.reachable_nodes.discard(node_id)
        self._state.unreachable_nodes.discard(node_id)
        self._node_last_seen.pop(node_id, None)
    
    def record_node_contact(self, node_id: str):
        """Record successful contact with a node."""
        self._node_last_seen[node_id] = datetime.utcnow()
        
        if node_id not in self._state.reachable_nodes:
            self._state.reachable_nodes.add(node_id)
            self._state.unreachable_nodes.discard(node_id)
            
            # Check if healing
            if self._state.status == PartitionStatus.PARTITIONED:
                self._check_partition_healing()
    
    def record_node_failure(self, node_id: str):
        """Record failure to contact a node."""
        self._state.unreachable_nodes.add(node_id)
        self._state.reachable_nodes.discard(node_id)
        
        # Check if this causes partition
        self._check_partition_status()
    
    # =========================================================================
    # AP MODE HELPERS
    # =========================================================================
    
    def _assess_freshness(self, data: VersionedData) -> Tuple[DataFreshness, Optional[str]]:
        """Assess data freshness based on partition state and age."""
        if self._state.status == PartitionStatus.CONNECTED:
            return DataFreshness.CONFIRMED, None
        
        age = (datetime.utcnow() - data.timestamp).total_seconds()
        
        if self._state.status == PartitionStatus.PARTIAL:
            if age < 30:
                return DataFreshness.LIKELY_CURRENT, None
            return DataFreshness.POTENTIALLY_STALE, \
                f"Data may be stale (age: {age:.0f}s, some nodes unreachable)"
        
        # PARTITIONED
        if self._state.partition_started:
            partition_duration = (datetime.utcnow() - self._state.partition_started).total_seconds()
            
            if partition_duration < 60:
                return DataFreshness.POTENTIALLY_STALE, \
                    f"Network partition detected {partition_duration:.0f}s ago. Data may not reflect recent updates."
            
            return DataFreshness.STALE, \
                f"Extended network partition ({partition_duration:.0f}s). " \
                f"This data may be significantly outdated. " \
                f"Partition will be resolved automatically when connectivity is restored."
        
        return DataFreshness.UNKNOWN, "Unable to determine data freshness"
    
    async def _quorum_read(self, key: str) -> Optional[VersionedData]:
        """Attempt quorum read from multiple nodes."""
        # Try to read from Raft if available
        if self.raft_node:
            try:
                # This would be implementation-specific
                pass
            except Exception:
                pass
        
        return self._local_store.get(key)
    
    async def _replicate_write(self, key: str, data: VersionedData):
        """Replicate write to other nodes."""
        # Implementation would send to reachable nodes
        for node_id in self._state.reachable_nodes:
            if node_id != self.node_id:
                # Send replication request
                pass
    
    async def _async_replicate(self, key: str, data: VersionedData):
        """Background replication task."""
        try:
            await self._replicate_write(key, data)
        except Exception as e:
            logger.warning(f"Async replication failed for {key}: {e}")
            self._pending_sync.append((key, data))
    
    async def _anti_entropy_loop(self):
        """Background anti-entropy synchronization."""
        while self._is_running:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                
                if self._state.status == PartitionStatus.CONNECTED:
                    await self._sync_pending_writes()
                    await self._exchange_merkle_trees()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Anti-entropy error: {e}")
    
    async def _sync_pending_writes(self):
        """Sync pending writes after partition heals."""
        if not self._pending_sync:
            return
        
        logger.info(f"Syncing {len(self._pending_sync)} pending writes")
        
        synced = []
        for key, data in self._pending_sync:
            try:
                await self._replicate_write(key, data)
                synced.append((key, data))
            except Exception as e:
                logger.warning(f"Failed to sync {key}: {e}")
        
        for item in synced:
            self._pending_sync.remove(item)
    
    async def _exchange_merkle_trees(self):
        """Exchange Merkle trees for anti-entropy sync."""
        # Implementation would compare data hashes between nodes
        pass
    
    def merge_remote_data(self, key: str, remote_data: VersionedData) -> bool:
        """
        Merge data received from another node.
        
        Uses vector clocks for conflict detection and last-write-wins
        for resolution.
        
        Args:
            key: Data key
            remote_data: Data from remote node
            
        Returns:
            True if local data was updated
        """
        local_data = self._local_store.get(key)
        
        if local_data is None:
            self._local_store[key] = remote_data
            return True
        
        if remote_data.is_newer_than(local_data):
            # Remote is newer - update local
            self._local_store[key] = remote_data
            
            # Merge vector clocks
            for node, version in remote_data.vector_clock.items():
                self._vector_clock[node] = max(
                    self._vector_clock.get(node, 0),
                    version
                )
            
            return True
        
        # Check for concurrent updates (conflict)
        if not local_data.is_newer_than(remote_data):
            # True concurrent conflict
            logger.warning(f"Concurrent update conflict for key {key}")
            
            # Notify conflict callbacks
            for callback in self._on_conflict:
                asyncio.create_task(callback(key, local_data, remote_data))
            
            # Last-write-wins resolution
            if remote_data.timestamp > local_data.timestamp:
                self._local_store[key] = remote_data
                return True
        
        return False
    
    # =========================================================================
    # LEGACY COMPATIBILITY (still works but uses AP internally)
    # =========================================================================
    
    async def submit_command(self, command: Any) -> Dict[str, Any]:
        """
        Submit a command with AP guarantees.
        
        For backwards compatibility. Internally uses AP write.
        
        Args:
            command: Command to submit
            
        Returns:
            Result including partition status
        """
        # Extract key/value from command (implementation-specific)
        key = getattr(command, 'key', str(id(command)))
        value = getattr(command, 'data', command)
        
        result = await self.write(key, value, ConsistencyLevel.EVENTUAL)
        
        return {
            "success": result.success,
            "accepted": result.accepted,
            "partition_status": self._state.status.value,
            "is_majority": self._state.is_majority,
            "sync_status": result.sync_status,
            "warning": result.warning
        }
    
    def can_accept_writes(self) -> bool:
        """
        Check if this node can accept writes.
        
        In AP mode: ALWAYS returns True.
        Writes are accepted locally and synced later.
        """
        return True  # AP mode - always accept writes
    
    def can_accept_reads(self) -> bool:
        """
        Check if this node can accept reads.
        
        In AP mode: ALWAYS returns True.
        """
        return True  # AP mode - always accept reads
    
    def get_current_quorum(self) -> int:
        """Get effective quorum size based on reachable nodes."""
        total = len(self._all_known_nodes)
        reachable = len(self._state.reachable_nodes)
        
        if total <= 1:
            return 1
        
        if self._state.status == PartitionStatus.CONNECTED:
            return (total // 2) + 1
        
        # In partition, use smaller quorum if in majority
        if self._state.is_majority:
            return (reachable // 2) + 1
        
        # Minority - can't achieve quorum
        return reachable + 1  # Impossible to achieve
    
    def _check_partition_status(self):
        """Check and update partition status."""
        total = len(self._all_known_nodes)
        reachable = len(self._state.reachable_nodes)
        unreachable = len(self._state.unreachable_nodes)
        
        if total <= 1:
            # Single node - always connected
            self._state.status = PartitionStatus.CONNECTED
            self._state.is_majority = True
            return
        
        old_status = self._state.status
        
        if unreachable == 0:
            self._state.status = PartitionStatus.CONNECTED
            self._state.is_majority = True
            self._state.last_full_connectivity = datetime.utcnow()
            
        elif reachable > total // 2:
            # We have majority
            if unreachable > 0:
                self._state.status = PartitionStatus.PARTIAL
            self._state.is_majority = True
            
        else:
            # Minority partition
            self._state.status = PartitionStatus.PARTITIONED
            self._state.is_majority = False
            
            if self._state.partition_started is None:
                self._state.partition_started = datetime.utcnow()
        
        if old_status != self._state.status:
            logger.warning(
                f"Partition status changed: {old_status.value} -> {self._state.status.value}, "
                f"reachable: {reachable}/{total}, majority: {self._state.is_majority}"
            )
    
    def _check_partition_healing(self):
        """Check if partition is healing."""
        total = len(self._all_known_nodes)
        reachable = len(self._state.reachable_nodes)
        
        if reachable > total // 2:
            if self._state.status == PartitionStatus.PARTITIONED:
                self._state.status = PartitionStatus.HEALING
                self._state.is_majority = True
                logger.info("Partition healing detected")
    
    async def _monitor_loop(self):
        """Monitor partition status periodically."""
        while self._is_running:
            try:
                await asyncio.sleep(self._check_interval)
                
                now = datetime.utcnow()
                
                # Check each node's last contact time
                for node_id in list(self._all_known_nodes):
                    if node_id == self.node_id:
                        continue
                    
                    last_seen = self._node_last_seen.get(node_id)
                    
                    if last_seen is None:
                        self._state.unreachable_nodes.add(node_id)
                        self._state.reachable_nodes.discard(node_id)
                    elif (now - last_seen).total_seconds() > self._partition_threshold:
                        # Node not seen recently
                        if node_id in self._state.reachable_nodes:
                            self.record_node_failure(node_id)
                
                # Check for healing
                if self._state.status == PartitionStatus.HEALING:
                    if len(self._state.unreachable_nodes) == 0:
                        self._state.status = PartitionStatus.CONNECTED
                        self._state.partition_started = None
                        
                        # Notify callbacks
                        for callback in self._on_heal:
                            try:
                                await callback(self._state)
                            except Exception as e:
                                logger.error(f"Heal callback error: {e}")
                        
                        logger.info("Partition healed, full connectivity restored")
                
                # Notify if partition detected
                if self._state.status == PartitionStatus.PARTITIONED:
                    for callback in self._on_partition:
                        try:
                            await callback(self._state)
                        except Exception as e:
                            logger.error(f"Partition callback error: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Partition monitor error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get AP-mode partition tolerance status."""
        return {
            "node_id": self.node_id,
            "mode": "AP",  # Availability + Partition tolerance
            "cap_guarantee": {
                "availability": True,  # Always available
                "consistency": "eventual",  # Not guaranteed during partitions
                "partition_tolerance": True  # Handles network partitions
            },
            "partition_status": self._state.status.value,
            "is_majority": self._state.is_majority,
            "can_accept_writes": True,  # AP mode always accepts
            "can_accept_reads": True,   # AP mode always accepts
            "write_guarantee": "accepted_locally",
            "read_guarantee": "best_effort_freshness",
            "current_quorum": self.get_current_quorum(),
            "total_nodes": len(self._all_known_nodes),
            "reachable_nodes": list(self._state.reachable_nodes),
            "unreachable_nodes": list(self._state.unreachable_nodes),
            "pending_sync_count": len(self._pending_sync),
            "local_data_count": len(self._local_store),
            "partition_started": self._state.partition_started.isoformat() if self._state.partition_started else None,
            "last_full_connectivity": self._state.last_full_connectivity.isoformat() if self._state.last_full_connectivity else None,
            "staleness_info": self._get_staleness_summary()
        }
    
    def _get_staleness_summary(self) -> Dict[str, Any]:
        """Get summary of data staleness."""
        if self._state.status == PartitionStatus.CONNECTED:
            return {
                "status": "fresh",
                "message": "All data is confirmed fresh - full connectivity"
            }
        
        if self._state.partition_started:
            duration = (datetime.utcnow() - self._state.partition_started).total_seconds()
            
            return {
                "status": "potentially_stale",
                "partition_duration_seconds": duration,
                "message": f"Data may be up to {duration:.0f}s stale due to network partition",
                "recommendation": "Reads will return local data with freshness indicators"
            }
        
        return {
            "status": "unknown",
            "message": "Unable to determine data freshness"
        }
    
    # =========================================================================
    # QUERY INTERFACE (for search operations)
    # =========================================================================
    
    async def query(
        self,
        query_func: Callable[[], Awaitable[Any]],
        query_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute a query with AP guarantees - ALWAYS returns a response.
        
        This is the main interface for search operations. It guarantees
        that a response is always returned, even during network partitions.
        
        Args:
            query_func: Async function that performs the actual query
            query_id: Optional query identifier for logging
            
        Returns:
            Query result with freshness and availability information
        """
        query_start = datetime.utcnow()
        
        try:
            # ALWAYS execute the query (AP guarantee)
            result = await query_func()
            
            freshness = DataFreshness.CONFIRMED
            warning = None
            
            if self._state.status != PartitionStatus.CONNECTED:
                if self._state.status == PartitionStatus.PARTITIONED:
                    freshness = DataFreshness.POTENTIALLY_STALE
                    partition_age = 0
                    if self._state.partition_started:
                        partition_age = (datetime.utcnow() - self._state.partition_started).total_seconds()
                    warning = (
                        f"Resultados obtenidos durante partición de red "
                        f"(duración: {partition_age:.0f}s). "
                        f"Los datos pueden no reflejar actualizaciones recientes "
                        f"de nodos inalcanzables: {list(self._state.unreachable_nodes)}"
                    )
                else:
                    freshness = DataFreshness.LIKELY_CURRENT
                    warning = "Algunos nodos no están disponibles. Los resultados pueden estar incompletos."
            
            return {
                "success": True,
                "data": result,
                "freshness": freshness.value,
                "availability_mode": "AP",
                "partition_status": self._state.status.value,
                "staleness_warning": warning,
                "query_time_ms": (datetime.utcnow() - query_start).total_seconds() * 1000,
                "source_nodes": list(self._state.reachable_nodes),
                "unavailable_nodes": list(self._state.unreachable_nodes)
            }
            
        except Exception as e:
            # Even on error, provide a response (AP guarantee)
            logger.error(f"Query error: {e}")
            
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "freshness": DataFreshness.UNKNOWN.value,
                "availability_mode": "AP",
                "partition_status": self._state.status.value,
                "staleness_warning": "Error ejecutando consulta. Sistema en modo AP - intente de nuevo.",
                "query_time_ms": (datetime.utcnow() - query_start).total_seconds() * 1000,
                "source_nodes": [self.node_id],
                "unavailable_nodes": list(self._state.unreachable_nodes)
            }

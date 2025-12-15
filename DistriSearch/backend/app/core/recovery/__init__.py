# -*- coding: utf-8 -*-
"""
Recovery Module - Handles failure detection and recovery.

Implements:
- Failure detection via heartbeat monitoring
- Automatic failover and replica promotion
- Re-replication of lost data
"""

from .failure_detector import FailureDetector, NodeHealth, FailureEvent
from .recovery_service import RecoveryService, RecoveryConfig, RecoveryTask
from .re_replication import ReReplicationManager, ReReplicationTask

__all__ = [
    "FailureDetector",
    "NodeHealth",
    "FailureEvent",
    "RecoveryService",
    "RecoveryConfig",
    "RecoveryTask",
    "ReReplicationManager",
    "ReReplicationTask",
]

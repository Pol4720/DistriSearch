# -*- coding: utf-8 -*-
"""
Partitioning Module - VP-Tree based document partitioning.

Implements Vantage-Point Tree for semantic document organization
across distributed nodes with efficient nearest-neighbor queries.
"""

from .vp_tree import VPTree, VPNode
from .partition_manager import PartitionManager
from .node_assignment import NodeAssigner, AssignmentStrategy
from .distance_metrics import DistanceCalculator, MetricType

__all__ = [
    "VPTree",
    "VPNode",
    "PartitionManager",
    "NodeAssigner",
    "AssignmentStrategy",
    "DistanceCalculator",
    "MetricType",
]

"""
DistriSearch Shared Package

This package contains shared code used by both master and slave nodes:
- Models: Data models for documents, nodes, clusters
- Protocols: Message formats and event definitions
- Constants: Configuration constants
"""

from shared.models import Document, Node, ClusterState
from shared.protocols import Message, Event
from shared.constants import config

__all__ = [
    'Document',
    'Node', 
    'ClusterState',
    'Message',
    'Event',
    'config'
]

__version__ = '1.0.0'

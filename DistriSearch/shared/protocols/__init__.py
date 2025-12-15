"""
Shared Protocols Package

Defines message formats and event types for inter-node communication.
"""

from shared.protocols.messages import (
    Message,
    MessageType,
    SearchRequest,
    SearchResponse,
    UploadRequest,
    UploadResponse,
    ReplicationRequest,
    ReplicationResponse,
    MigrationRequest,
    MigrationResponse
)
from shared.protocols.events import (
    Event,
    EventType,
    NodeJoinedEvent,
    NodeLeftEvent,
    NodeFailedEvent,
    DocumentIndexedEvent,
    RebalanceStartedEvent,
    RebalanceCompletedEvent,
    LeaderElectedEvent
)

__all__ = [
    # Messages
    'Message',
    'MessageType',
    'SearchRequest',
    'SearchResponse',
    'UploadRequest',
    'UploadResponse',
    'ReplicationRequest',
    'ReplicationResponse',
    'MigrationRequest',
    'MigrationResponse',
    # Events
    'Event',
    'EventType',
    'NodeJoinedEvent',
    'NodeLeftEvent',
    'NodeFailedEvent',
    'DocumentIndexedEvent',
    'RebalanceStartedEvent',
    'RebalanceCompletedEvent',
    'LeaderElectedEvent'
]

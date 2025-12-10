"""
Message Broker for internal communication.

Implements an in-memory message broker for:
- Publish/Subscribe messaging
- Request/Reply patterns
- Event distribution
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable, Set
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages in the system."""
    
    # Cluster events
    NODE_JOINED = "node_joined"
    NODE_LEFT = "node_left"
    NODE_FAILED = "node_failed"
    LEADER_ELECTED = "leader_elected"
    
    # Document events
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_UPDATED = "document_updated"
    
    # Replication events
    REPLICA_CREATED = "replica_created"
    REPLICA_DELETED = "replica_deleted"
    REPLICA_PROMOTED = "replica_promoted"
    
    # Search events
    SEARCH_REQUEST = "search_request"
    SEARCH_RESPONSE = "search_response"
    
    # Rebalancing events
    REBALANCE_STARTED = "rebalance_started"
    REBALANCE_COMPLETED = "rebalance_completed"
    PARTITION_MOVED = "partition_moved"
    
    # System events
    CONFIG_UPDATED = "config_updated"
    HEALTH_CHECK = "health_check"
    SHUTDOWN = "shutdown"
    
    # Custom
    CUSTOM = "custom"


@dataclass
class Message:
    """
    A message in the broker.
    
    Attributes:
        id: Unique message identifier
        type: Type of message
        source: Source node ID
        target: Target node ID (None for broadcast)
        payload: Message data
        timestamp: When message was created
        correlation_id: ID for request/reply correlation
        reply_to: Topic to reply to
    """
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    target: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data["type"]),
            source=data.get("source"),
            target=data.get("target"),
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )
    
    def create_reply(self, payload: Dict[str, Any]) -> "Message":
        """Create a reply message."""
        return Message(
            type=self.type,
            source=self.target,
            target=self.source,
            payload=payload,
            correlation_id=self.correlation_id or self.id,
        )


# Callback type for message handlers
MessageHandler = Callable[[Message], Awaitable[None]]


class Subscription:
    """
    A subscription to messages.
    
    Attributes:
        id: Unique subscription ID
        topic: Topic pattern (message type or wildcard)
        handler: Async handler function
        filter_func: Optional filter function
    """
    
    def __init__(
        self,
        topic: str,
        handler: MessageHandler,
        filter_func: Optional[Callable[[Message], bool]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.topic = topic
        self.handler = handler
        self.filter_func = filter_func
    
    def matches(self, message: Message) -> bool:
        """Check if subscription matches message."""
        # Check topic
        if self.topic != "*" and self.topic != message.type.value:
            return False
        
        # Check filter
        if self.filter_func and not self.filter_func(message):
            return False
        
        return True


class MessageBroker:
    """
    In-memory message broker for internal communication.
    
    Features:
    - Publish/Subscribe with topic filtering
    - Request/Reply pattern with correlation
    - Message persistence (optional)
    - Dead letter handling
    """
    
    def __init__(
        self,
        node_id: str,
        max_queue_size: int = 10000,
        enable_persistence: bool = False,
    ):
        """
        Initialize message broker.
        
        Args:
            node_id: This node's ID
            max_queue_size: Maximum pending messages
            enable_persistence: Enable message persistence
        """
        self.node_id = node_id
        self.max_queue_size = max_queue_size
        self.enable_persistence = enable_persistence
        
        # Subscriptions by topic
        self._subscriptions: Dict[str, List[Subscription]] = {}
        
        # Message queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        
        # Pending replies (correlation_id -> Future)
        self._pending_replies: Dict[str, asyncio.Future] = {}
        
        # Dead letter queue
        self._dead_letters: List[Message] = []
        self._max_dead_letters = 1000
        
        # Processing task
        self._process_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self._published_count = 0
        self._delivered_count = 0
        self._failed_count = 0
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info(f"MessageBroker initialized for node {node_id}")
    
    async def start(self):
        """Start the message broker."""
        if self._running:
            return
        
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("MessageBroker started")
    
    async def stop(self):
        """Stop the message broker."""
        self._running = False
        
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        # Cancel pending replies
        for future in self._pending_replies.values():
            if not future.done():
                future.cancel()
        
        logger.info("MessageBroker stopped")
    
    def subscribe(
        self,
        topic: str,
        handler: MessageHandler,
        filter_func: Optional[Callable[[Message], bool]] = None,
    ) -> str:
        """
        Subscribe to messages on a topic.
        
        Args:
            topic: Topic to subscribe to (message type or "*" for all)
            handler: Async handler function
            filter_func: Optional message filter
            
        Returns:
            Subscription ID
        """
        sub = Subscription(topic, handler, filter_func)
        
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(sub)
        
        logger.debug(f"Subscribed to topic '{topic}' with ID {sub.id}")
        return sub.id
    
    def unsubscribe(self, subscription_id: str):
        """
        Unsubscribe from messages.
        
        Args:
            subscription_id: Subscription ID to remove
        """
        for topic, subs in self._subscriptions.items():
            self._subscriptions[topic] = [
                s for s in subs if s.id != subscription_id
            ]
        
        logger.debug(f"Unsubscribed {subscription_id}")
    
    async def publish(self, message: Message):
        """
        Publish a message.
        
        Args:
            message: Message to publish
        """
        # Set source if not set
        if message.source is None:
            message.source = self.node_id
        
        try:
            self._queue.put_nowait(message)
            self._published_count += 1
        except asyncio.QueueFull:
            logger.warning("Message queue full, adding to dead letters")
            self._add_dead_letter(message)
    
    async def publish_and_wait(
        self,
        message: Message,
        timeout: float = 30.0,
    ) -> Optional[Message]:
        """
        Publish message and wait for reply.
        
        Args:
            message: Message to publish
            timeout: Reply timeout in seconds
            
        Returns:
            Reply message or None on timeout
        """
        # Set up reply handling
        correlation_id = message.id
        message.correlation_id = correlation_id
        
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_replies[correlation_id] = future
        
        try:
            # Publish message
            await self.publish(message)
            
            # Wait for reply
            reply = await asyncio.wait_for(future, timeout=timeout)
            return reply
            
        except asyncio.TimeoutError:
            logger.warning(f"Reply timeout for message {message.id}")
            return None
            
        finally:
            self._pending_replies.pop(correlation_id, None)
    
    async def _process_loop(self):
        """Process messages from the queue."""
        try:
            while self._running:
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=0.1,
                    )
                    await self._deliver_message(message)
                except asyncio.TimeoutError:
                    continue
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _deliver_message(self, message: Message):
        """Deliver message to matching subscribers."""
        # Check if it's a reply to a pending request
        if message.correlation_id in self._pending_replies:
            future = self._pending_replies[message.correlation_id]
            if not future.done():
                future.set_result(message)
            return
        
        # Find matching subscriptions
        matching_subs: List[Subscription] = []
        
        # Check specific topic
        topic = message.type.value
        if topic in self._subscriptions:
            for sub in self._subscriptions[topic]:
                if sub.matches(message):
                    matching_subs.append(sub)
        
        # Check wildcard subscriptions
        if "*" in self._subscriptions:
            for sub in self._subscriptions["*"]:
                if sub.matches(message):
                    matching_subs.append(sub)
        
        # Deliver to subscribers
        if not matching_subs:
            self._add_dead_letter(message)
            return
        
        for sub in matching_subs:
            try:
                await sub.handler(message)
                self._delivered_count += 1
            except Exception as e:
                self._failed_count += 1
                logger.error(
                    f"Error delivering message {message.id} "
                    f"to subscription {sub.id}: {e}"
                )
    
    def _add_dead_letter(self, message: Message):
        """Add message to dead letter queue."""
        self._dead_letters.append(message)
        
        # Trim if needed
        if len(self._dead_letters) > self._max_dead_letters:
            self._dead_letters = self._dead_letters[-self._max_dead_letters:]
    
    def get_dead_letters(self) -> List[Message]:
        """Get dead letter messages."""
        return self._dead_letters.copy()
    
    def clear_dead_letters(self):
        """Clear dead letter queue."""
        self._dead_letters.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        return {
            "node_id": self.node_id,
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "subscriptions": sum(len(s) for s in self._subscriptions.values()),
            "pending_replies": len(self._pending_replies),
            "dead_letters": len(self._dead_letters),
            "published_count": self._published_count,
            "delivered_count": self._delivered_count,
            "failed_count": self._failed_count,
        }


class EventBus:
    """
    High-level event bus built on MessageBroker.
    
    Provides simplified pub/sub interface for cluster events.
    """
    
    def __init__(self, broker: MessageBroker):
        """
        Initialize event bus.
        
        Args:
            broker: Underlying message broker
        """
        self.broker = broker
        self._handlers: Dict[MessageType, List[MessageHandler]] = {}
    
    def on(
        self,
        event_type: MessageType,
        handler: MessageHandler,
    ):
        """
        Register event handler.
        
        Args:
            event_type: Event type to handle
            handler: Async handler function
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
            
            # Subscribe to broker
            self.broker.subscribe(
                event_type.value,
                self._dispatch_event,
            )
        
        self._handlers[event_type].append(handler)
    
    async def emit(
        self,
        event_type: MessageType,
        data: Dict[str, Any],
        target: Optional[str] = None,
    ):
        """
        Emit an event.
        
        Args:
            event_type: Type of event
            data: Event data
            target: Optional target node
        """
        message = Message(
            type=event_type,
            payload=data,
            target=target,
        )
        await self.broker.publish(message)
    
    async def _dispatch_event(self, message: Message):
        """Dispatch event to registered handlers."""
        handlers = self._handlers.get(message.type, [])
        
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(
                    f"Event handler error for {message.type.value}: {e}"
                )

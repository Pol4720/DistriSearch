# -*- coding: utf-8 -*-
"""
Node Communication Tests

Tests to verify inter-node communication:
- Heartbeat mechanism
- Message broker functionality
- REST client for node-to-node calls
- WebSocket communication
- Failure detection
- Service discovery
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

from app.distributed.communication.heartbeat import (
    HeartbeatService,
    NodeHeartbeat,
    NodeInfo,
    NodeStatus,
)
from app.distributed.communication.message_broker import (
    MessageBroker,
    Message,
    MessageType,
)
from app.distributed.communication.rest_client import (
    RESTClient,
    RESTResponse,
)
from app.distributed.coordination.service_discovery import (
    ServiceEndpoint,
    ServiceType,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def heartbeat_service() -> HeartbeatService:
    """Create heartbeat service."""
    return HeartbeatService(
        heartbeat_interval=1.0,
        suspect_threshold=3,
        dead_threshold=6,
    )


@pytest.fixture
def message_broker() -> MessageBroker:
    """Create message broker."""
    return MessageBroker(node_id="node-1")


@pytest.fixture
def rest_client() -> RESTClient:
    """Create REST client."""
    return RESTClient(
        base_url="http://localhost:8000",
        timeout=5.0,
        max_retries=3,
    )


# ============================================================================
# Heartbeat Tests
# ============================================================================

class TestHeartbeat:
    """Tests for heartbeat mechanism."""
    
    def test_heartbeat_creation(self):
        """Test creating a heartbeat."""
        heartbeat = NodeHeartbeat(
            node_id="node-1",
            load=0.5,
            documents_count=1000,
            cpu_usage=0.4,
            memory_usage=0.6,
        )
        
        assert heartbeat.node_id == "node-1"
        assert heartbeat.load == 0.5
        assert heartbeat.documents_count == 1000
    
    def test_heartbeat_serialization(self):
        """Test heartbeat serialization/deserialization."""
        heartbeat = NodeHeartbeat(
            node_id="node-1",
            timestamp=datetime.now(),
            load=0.5,
            documents_count=1000,
        )
        
        # Serialize
        data = heartbeat.to_dict()
        
        # Deserialize
        restored = NodeHeartbeat.from_dict(data)
        
        assert restored.node_id == heartbeat.node_id
        assert restored.load == heartbeat.load
        assert restored.documents_count == heartbeat.documents_count
    
    @pytest.mark.asyncio
    async def test_register_node(self, heartbeat_service):
        """Test registering a new node."""
        await heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        node_status = heartbeat_service.get_node_status("node-2")
        
        assert node_status == NodeStatus.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_receive_heartbeat_updates_status(self, heartbeat_service):
        """Test that receiving heartbeat updates node status."""
        await heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        heartbeat = NodeHeartbeat(
            node_id="node-2",
            timestamp=datetime.now(),
            load=0.3,
        )
        
        await heartbeat_service.receive_heartbeat(heartbeat)
        
        node_status = heartbeat_service.get_node_status("node-2")
        assert node_status == NodeStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_get_healthy_nodes(self, heartbeat_service):
        """Test getting list of healthy nodes."""
        # Register multiple nodes
        await heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        await heartbeat_service.register_node("node-3", "192.168.1.3:8000")
        await heartbeat_service.register_node("node-4", "192.168.1.4:8000")
        
        # Make node-2 healthy
        await heartbeat_service.receive_heartbeat(NodeHeartbeat(
            node_id="node-2",
            timestamp=datetime.now(),
        ))
        
        # Make node-3 healthy
        await heartbeat_service.receive_heartbeat(NodeHeartbeat(
            node_id="node-3",
            timestamp=datetime.now(),
        ))
        
        # Leave node-4 as unknown
        
        healthy = heartbeat_service.get_healthy_nodes()
        
        assert "node-2" in healthy
        assert "node-3" in healthy
        assert "node-4" not in healthy


# ============================================================================
# Message Broker Tests
# ============================================================================

class TestMessageBroker:
    """Tests for message broker functionality."""
    
    def test_create_message(self):
        """Test creating a message."""
        message = Message(
            type=MessageType.DOCUMENT_INDEXED,
            source="node-1",
            target="node-2",
            payload={"doc_id": "doc-1", "data": "content"},
        )
        
        assert message.source == "node-1"
        assert message.type == MessageType.DOCUMENT_INDEXED
        assert message.target == "node-2"
    
    def test_message_serialization(self):
        """Test message serialization."""
        message = Message(
            type=MessageType.HEALTH_CHECK,
            source="node-1",
            target="node-2",
            payload={"load": 0.5},
            timestamp=datetime.now(),
        )
        
        data = message.to_dict()
        restored = Message.from_dict(data)
        
        assert restored.id == message.id
        assert restored.source == message.source
        assert restored.type == message.type
    
    @pytest.mark.asyncio
    async def test_subscribe_to_message_type(self, message_broker):
        """Test subscribing to message types."""
        received_messages = []
        
        async def handler(message: Message):
            received_messages.append(message)
        
        # Start the broker's processing loop
        await message_broker.start()
        
        try:
            message_broker.subscribe(MessageType.DOCUMENT_INDEXED.value, handler)
            
            # Simulate receiving a message
            message = Message(
                source="node-2",
                target="node-1",
                type=MessageType.DOCUMENT_INDEXED,
                payload={"doc_id": "doc-1"},
                timestamp=datetime.now(),
            )
            
            await message_broker.publish(message)
            await asyncio.sleep(0.2)  # Let handlers run
            
            assert len(received_messages) == 1
            assert received_messages[0].payload["doc_id"] == "doc-1"
        finally:
            await message_broker.stop()


# ============================================================================
# REST Client Tests
# ============================================================================

class TestRESTClient:
    """Tests for REST client inter-node communication."""
    
    @pytest.mark.asyncio
    async def test_response_success_property(self):
        """Test RESTResponse success property."""
        success_response = RESTResponse(status=200, data={"ok": True})
        assert success_response.success is True
        
        error_response = RESTResponse(status=500, error="Server error")
        assert error_response.success is False
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, rest_client):
        """Test REST client initialization."""
        assert rest_client.base_url == "http://localhost:8000"
        assert rest_client.max_retries == 3


# ============================================================================
# Service Discovery Tests
# ============================================================================

class TestServiceDiscovery:
    """Tests for service discovery mechanism."""
    
    def test_service_endpoint_creation(self):
        """Test creating a service endpoint."""
        endpoint = ServiceEndpoint(
            service_type=ServiceType.SLAVE,
            node_id="node-1",
            address="192.168.1.1:8000",
            healthy=True,
        )
        
        assert endpoint.node_id == "node-1"
        assert endpoint.service_type == ServiceType.SLAVE
        assert endpoint.healthy is True
    
    def test_service_endpoint_host_port(self):
        """Test extracting host and port from address."""
        endpoint = ServiceEndpoint(
            service_type=ServiceType.MASTER,
            node_id="master-1",
            address="192.168.1.1:9000",
        )
        
        assert endpoint.host == "192.168.1.1"
        assert endpoint.port == 9000
    
    def test_service_endpoint_serialization(self):
        """Test service endpoint serialization."""
        endpoint = ServiceEndpoint(
            service_type=ServiceType.SLAVE,
            node_id="node-1",
            address="192.168.1.1:8000",
            healthy=True,
            metadata={"version": "1.0"},
        )
        
        data = endpoint.to_dict()
        
        assert data["service_type"] == "slave"
        assert data["node_id"] == "node-1"
        assert data["address"] == "192.168.1.1:8000"


# ============================================================================
# Node Info Tests
# ============================================================================

class TestNodeInfo:
    """Tests for node information tracking."""
    
    def test_node_info_creation(self):
        """Test creating node info."""
        node_info = NodeInfo(
            node_id="node-1",
            address="192.168.1.1:8000",
            status=NodeStatus.HEALTHY,
        )
        
        assert node_info.node_id == "node-1"
        assert node_info.address == "192.168.1.1:8000"
        assert node_info.status == NodeStatus.HEALTHY
    
    def test_time_since_last_heartbeat_with_none(self):
        """Test time since heartbeat when no heartbeat received."""
        node_info = NodeInfo(
            node_id="node-1",
            address="192.168.1.1:8000",
        )
        
        # No heartbeat received, should return infinity
        assert node_info.time_since_last_heartbeat() == float('inf')
    
    def test_time_since_last_heartbeat_with_recent(self):
        """Test time since heartbeat with recent heartbeat."""
        heartbeat = NodeHeartbeat(
            node_id="node-1",
            timestamp=datetime.now() - timedelta(seconds=5),
        )
        
        node_info = NodeInfo(
            node_id="node-1",
            address="192.168.1.1:8000",
            last_heartbeat=heartbeat,
        )
        
        time_since = node_info.time_since_last_heartbeat()
        assert 4.9 < time_since < 5.5


# ============================================================================
# Integration Tests
# ============================================================================

class TestCommunicationIntegration:
    """Integration tests for node communication."""
    
    @pytest.mark.asyncio
    async def test_full_node_lifecycle(self, heartbeat_service):
        """Test complete node lifecycle: join, heartbeat, leave."""
        # Node-2 joins
        await heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Node-2 sends heartbeats
        for _ in range(3):
            heartbeat = NodeHeartbeat(
                node_id="node-2",
                timestamp=datetime.now(),
                load=0.3,
            )
            await heartbeat_service.receive_heartbeat(heartbeat)
            await asyncio.sleep(0.01)
        
        assert heartbeat_service.get_node_status("node-2") == NodeStatus.HEALTHY
        
        # Node-2 is unregistered
        await heartbeat_service.unregister_node("node-2")
        
        assert heartbeat_service.get_node_status("node-2") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

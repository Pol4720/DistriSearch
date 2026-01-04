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
    RestClient,
    NodeEndpoint,
)
from app.distributed.coordination.service_discovery import (
    ServiceDiscovery,
    ServiceInfo,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def heartbeat_service() -> HeartbeatService:
    """Create heartbeat service."""
    return HeartbeatService(
        node_id="node-1",
        heartbeat_interval_sec=1.0,
        failure_threshold=3,
        suspect_threshold=2,
    )


@pytest.fixture
def message_broker() -> MessageBroker:
    """Create message broker."""
    return MessageBroker(node_id="node-1")


@pytest.fixture
def rest_client() -> RestClient:
    """Create REST client."""
    return RestClient(
        timeout_sec=5.0,
        max_retries=3,
    )


@pytest.fixture
def service_discovery() -> ServiceDiscovery:
    """Create service discovery."""
    return ServiceDiscovery(
        node_id="node-1",
        discovery_interval_sec=30.0,
    )


# ============================================================================
# Heartbeat Tests
# ============================================================================

class TestHeartbeat:
    """Tests for heartbeat mechanism."""
    
    def test_create_heartbeat(self, heartbeat_service):
        """Test creating a heartbeat."""
        heartbeat = heartbeat_service.create_heartbeat(
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
            timestamp=datetime.utcnow(),
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
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        node_info = heartbeat_service.get_node_info("node-2")
        
        assert node_info is not None
        assert node_info.address == "192.168.1.2:8000"
        assert node_info.status == NodeStatus.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_receive_heartbeat_updates_status(self, heartbeat_service):
        """Test that receiving heartbeat updates node status."""
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        heartbeat = NodeHeartbeat(
            node_id="node-2",
            timestamp=datetime.utcnow(),
            load=0.3,
        )
        
        heartbeat_service.receive_heartbeat(heartbeat)
        
        node_info = heartbeat_service.get_node_info("node-2")
        assert node_info.status == NodeStatus.HEALTHY
        assert node_info.last_heartbeat is not None
    
    @pytest.mark.asyncio
    async def test_missed_heartbeats_makes_suspect(self, heartbeat_service):
        """Test that missed heartbeats changes status to suspect."""
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Send initial heartbeat
        old_heartbeat = NodeHeartbeat(
            node_id="node-2",
            timestamp=datetime.utcnow() - timedelta(seconds=10),
            load=0.3,
        )
        heartbeat_service.receive_heartbeat(old_heartbeat)
        
        # Simulate time passing and check
        heartbeat_service._check_node_health("node-2", missed_count=2)
        
        node_info = heartbeat_service.get_node_info("node-2")
        assert node_info.status == NodeStatus.SUSPECT
    
    @pytest.mark.asyncio
    async def test_many_missed_heartbeats_marks_dead(self, heartbeat_service):
        """Test that many missed heartbeats marks node as dead."""
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Simulate many missed heartbeats
        heartbeat_service._check_node_health("node-2", missed_count=5)
        
        node_info = heartbeat_service.get_node_info("node-2")
        assert node_info.status == NodeStatus.DEAD
    
    @pytest.mark.asyncio
    async def test_get_healthy_nodes(self, heartbeat_service):
        """Test getting list of healthy nodes."""
        # Register multiple nodes
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        heartbeat_service.register_node("node-3", "192.168.1.3:8000")
        heartbeat_service.register_node("node-4", "192.168.1.4:8000")
        
        # Make node-2 healthy
        heartbeat_service.receive_heartbeat(NodeHeartbeat(
            node_id="node-2",
            timestamp=datetime.utcnow(),
        ))
        
        # Make node-3 healthy
        heartbeat_service.receive_heartbeat(NodeHeartbeat(
            node_id="node-3",
            timestamp=datetime.utcnow(),
        ))
        
        # Leave node-4 as unknown
        
        healthy = heartbeat_service.get_healthy_nodes()
        
        assert "node-2" in healthy
        assert "node-3" in healthy
        assert "node-4" not in healthy
    
    @pytest.mark.asyncio
    async def test_heartbeat_callback_on_failure(self, heartbeat_service):
        """Test callback is triggered on node failure."""
        failed_nodes = []
        
        def on_failure(node_id: str):
            failed_nodes.append(node_id)
        
        heartbeat_service.on_node_failure = on_failure
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Simulate failure
        heartbeat_service._mark_node_dead("node-2")
        
        assert "node-2" in failed_nodes


# ============================================================================
# Message Broker Tests
# ============================================================================

class TestMessageBroker:
    """Tests for message broker functionality."""
    
    def test_create_message(self, message_broker):
        """Test creating a message."""
        message = message_broker.create_message(
            type=MessageType.DOCUMENT_SYNC,
            payload={"doc_id": "doc-1", "data": "content"},
            target_node="node-2",
        )
        
        assert message.sender == "node-1"
        assert message.type == MessageType.DOCUMENT_SYNC
        assert message.target == "node-2"
    
    def test_message_serialization(self):
        """Test message serialization."""
        message = Message(
            id="msg-1",
            sender="node-1",
            target="node-2",
            type=MessageType.HEARTBEAT,
            payload={"load": 0.5},
            timestamp=datetime.utcnow(),
        )
        
        data = message.to_dict()
        restored = Message.from_dict(data)
        
        assert restored.id == message.id
        assert restored.sender == message.sender
        assert restored.type == message.type
    
    @pytest.mark.asyncio
    async def test_subscribe_to_message_type(self, message_broker):
        """Test subscribing to message types."""
        received_messages = []
        
        async def handler(message: Message):
            received_messages.append(message)
        
        message_broker.subscribe(MessageType.DOCUMENT_SYNC, handler)
        
        # Simulate receiving a message
        message = Message(
            id="msg-1",
            sender="node-2",
            target="node-1",
            type=MessageType.DOCUMENT_SYNC,
            payload={"doc_id": "doc-1"},
            timestamp=datetime.utcnow(),
        )
        
        await message_broker.dispatch(message)
        
        assert len(received_messages) == 1
        assert received_messages[0].id == "msg-1"
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, message_broker):
        """Test broadcasting message to all nodes."""
        sent_to = []
        
        async def mock_send(node_id: str, message: Message):
            sent_to.append(node_id)
        
        message_broker._send_func = mock_send
        message_broker.known_nodes = {"node-2", "node-3", "node-4"}
        
        message = message_broker.create_message(
            type=MessageType.CLUSTER_STATE,
            payload={"leader": "node-1"},
        )
        
        await message_broker.broadcast(message)
        
        assert "node-2" in sent_to
        assert "node-3" in sent_to
        assert "node-4" in sent_to
    
    @pytest.mark.asyncio
    async def test_request_response_pattern(self, message_broker):
        """Test request-response message pattern."""
        async def mock_send(node_id: str, message: Message):
            # Simulate response
            response = Message(
                id=f"resp-{message.id}",
                sender=node_id,
                target=message.sender,
                type=MessageType.RESPONSE,
                payload={"result": "success"},
                correlation_id=message.id,
                timestamp=datetime.utcnow(),
            )
            await message_broker.dispatch(response)
        
        message_broker._send_func = mock_send
        
        response = await message_broker.request(
            target_node="node-2",
            type=MessageType.QUERY,
            payload={"query": "test"},
            timeout_sec=5.0,
        )
        
        assert response is not None
        assert response.payload["result"] == "success"


# ============================================================================
# REST Client Tests
# ============================================================================

class TestRestClient:
    """Tests for REST client inter-node communication."""
    
    @pytest.mark.asyncio
    async def test_get_request(self, rest_client):
        """Test GET request to another node."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await rest_client.get(
                node_address="192.168.1.2:8000",
                endpoint="/health",
            )
            
            assert result["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_post_request(self, rest_client):
        """Test POST request to another node."""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"created": True})
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await rest_client.post(
                node_address="192.168.1.2:8000",
                endpoint="/documents",
                data={"doc_id": "doc-1", "content": "test"},
            )
            
            assert result["created"] is True
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, rest_client):
        """Test retry logic on request failure."""
        call_count = 0
        
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection refused")
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True})
            return mock_response
        
        with patch('aiohttp.ClientSession.get', side_effect=mock_request):
            result = await rest_client.get(
                node_address="192.168.1.2:8000",
                endpoint="/health",
            )
        
        assert call_count == 3
        assert result["ok"] is True
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, rest_client):
        """Test request timeout handling."""
        rest_client.timeout_sec = 0.1
        
        async def slow_request(*args, **kwargs):
            await asyncio.sleep(1.0)
        
        with patch('aiohttp.ClientSession.get', side_effect=slow_request):
            with pytest.raises(asyncio.TimeoutError):
                await rest_client.get(
                    node_address="192.168.1.2:8000",
                    endpoint="/slow",
                )


# ============================================================================
# Service Discovery Tests
# ============================================================================

class TestServiceDiscovery:
    """Tests for service discovery mechanism."""
    
    @pytest.mark.asyncio
    async def test_register_service(self, service_discovery):
        """Test registering a service."""
        service_discovery.register_service(
            service_name="backend",
            address="192.168.1.1",
            port=8000,
            metadata={"version": "1.0"},
        )
        
        services = service_discovery.get_services("backend")
        
        assert len(services) == 1
        assert services[0].address == "192.168.1.1"
        assert services[0].port == 8000
    
    @pytest.mark.asyncio
    async def test_discover_nodes(self, service_discovery):
        """Test discovering other nodes."""
        # Register multiple nodes
        for i in range(1, 4):
            service_discovery.register_service(
                service_name="distrisearch-node",
                address=f"192.168.1.{i}",
                port=8000,
                node_id=f"node-{i}",
            )
        
        nodes = service_discovery.discover_nodes()
        
        assert len(nodes) == 3
    
    @pytest.mark.asyncio
    async def test_deregister_service(self, service_discovery):
        """Test deregistering a service."""
        service_discovery.register_service(
            service_name="backend",
            address="192.168.1.1",
            port=8000,
            node_id="node-1",
        )
        
        service_discovery.deregister_service("node-1", "backend")
        
        services = service_discovery.get_services("backend")
        assert len(services) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_filtering(self, service_discovery):
        """Test that only healthy services are returned."""
        # Register healthy service
        service_discovery.register_service(
            service_name="backend",
            address="192.168.1.1",
            port=8000,
            healthy=True,
        )
        
        # Register unhealthy service
        service_discovery.register_service(
            service_name="backend",
            address="192.168.1.2",
            port=8000,
            healthy=False,
        )
        
        healthy_services = service_discovery.get_healthy_services("backend")
        
        assert len(healthy_services) == 1
        assert healthy_services[0].address == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_dns_based_discovery(self, service_discovery):
        """Test DNS-based service discovery."""
        # Mock DNS resolution
        with patch.object(service_discovery, '_resolve_dns') as mock_dns:
            mock_dns.return_value = [
                ("192.168.1.1", 8000),
                ("192.168.1.2", 8000),
                ("192.168.1.3", 8000),
            ]
            
            nodes = await service_discovery.discover_via_dns("distrisearch.local")
            
            assert len(nodes) == 3


# ============================================================================
# Failure Detection Tests
# ============================================================================

class TestFailureDetection:
    """Tests for node failure detection."""
    
    @pytest.mark.asyncio
    async def test_phi_accrual_failure_detector(self, heartbeat_service):
        """Test phi accrual failure detection algorithm."""
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Send regular heartbeats
        for i in range(10):
            heartbeat = NodeHeartbeat(
                node_id="node-2",
                timestamp=datetime.utcnow(),
            )
            heartbeat_service.receive_heartbeat(heartbeat)
            await asyncio.sleep(0.01)
        
        # Calculate phi (suspicion level)
        phi = heartbeat_service.calculate_phi("node-2")
        
        # Should be low (node is healthy)
        assert phi < 1.0
    
    @pytest.mark.asyncio
    async def test_failure_detector_adapts_to_network(self, heartbeat_service):
        """Test that failure detector adapts to network conditions."""
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Simulate variable latency heartbeats
        base_time = datetime.utcnow()
        delays = [0.1, 0.15, 0.12, 0.2, 0.11]
        
        for delay in delays:
            heartbeat = NodeHeartbeat(
                node_id="node-2",
                timestamp=base_time + timedelta(seconds=delay),
            )
            heartbeat_service.receive_heartbeat(heartbeat)
        
        # Get estimated interval
        interval = heartbeat_service.get_estimated_interval("node-2")
        
        # Should have learned the average interval
        assert interval is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestCommunicationIntegration:
    """Integration tests for node communication."""
    
    @pytest.mark.asyncio
    async def test_full_node_lifecycle(self, heartbeat_service, message_broker):
        """Test complete node lifecycle: join, heartbeat, leave."""
        # Node-2 joins
        heartbeat_service.register_node("node-2", "192.168.1.2:8000")
        
        # Node-2 sends heartbeats
        for _ in range(3):
            heartbeat = NodeHeartbeat(
                node_id="node-2",
                timestamp=datetime.utcnow(),
                load=0.3,
            )
            heartbeat_service.receive_heartbeat(heartbeat)
            await asyncio.sleep(0.01)
        
        assert heartbeat_service.get_node_info("node-2").status == NodeStatus.HEALTHY
        
        # Node-2 leaves (stops heartbeating)
        heartbeat_service._mark_node_dead("node-2")
        
        assert heartbeat_service.get_node_info("node-2").status == NodeStatus.DEAD
    
    @pytest.mark.asyncio
    async def test_cluster_state_propagation(self, message_broker):
        """Test cluster state propagation to all nodes."""
        received_by = []
        
        async def mock_send(node_id: str, message: Message):
            received_by.append(node_id)
        
        message_broker._send_func = mock_send
        message_broker.known_nodes = {"node-2", "node-3", "node-4"}
        
        # Broadcast cluster state update
        state_update = message_broker.create_message(
            type=MessageType.CLUSTER_STATE,
            payload={
                "leader": "node-1",
                "term": 5,
                "nodes": ["node-1", "node-2", "node-3", "node-4"],
            },
        )
        
        await message_broker.broadcast(state_update)
        
        # All nodes should receive the update
        assert set(received_by) == {"node-2", "node-3", "node-4"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])

import asyncio
from datetime import datetime

# Importar desde el nuevo módulo cluster
from cluster.heartbeat import HeartbeatService, HeartbeatState
from core.models import MessageType, NodeStatus, ClusterMessage


class DummySocket:
    def __init__(self):
        self.sent = []

    def sendto(self, data, addr):
        self.sent.append((data, addr))


def test_heartbeat_state_timeout_marks_offline():
    state = HeartbeatState("node-x")
    assert state.status == NodeStatus.UNKNOWN

    timed_out = state.check_timeout(timeout_seconds=0)
    assert timed_out is True
    assert state.status == NodeStatus.OFFLINE
    assert state.missed_beats == 1


def test_handle_ping_updates_peer_and_replies():
    svc = HeartbeatService(node_id="node-a", port=0, heartbeat_interval=1, heartbeat_timeout=1)
    svc._socket = DummySocket()
    svc.add_peer("node-b", "127.0.0.1", 9999)

    message = ClusterMessage(type=MessageType.PING, sender_id="node-b", payload={}, timestamp=datetime.utcnow())

    async def _run():
        await svc._handle_message(message, ("127.0.0.1", 9999))

    asyncio.run(_run())

    assert "node-b" in svc.get_online_peers()
    assert svc._socket.sent  # respondió con PONG


def test_handle_pong_marks_peer_online():
    svc = HeartbeatService(node_id="node-a", port=0, heartbeat_interval=1, heartbeat_timeout=1)
    svc._socket = DummySocket()
    svc.add_peer("node-b", "127.0.0.1", 9999)

    message = ClusterMessage(type=MessageType.PONG, sender_id="node-b", payload={}, timestamp=datetime.utcnow())

    async def _run():
        await svc._handle_message(message, ("127.0.0.1", 9999))

    asyncio.run(_run())

    assert "node-b" in svc.get_online_peers()

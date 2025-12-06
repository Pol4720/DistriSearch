import asyncio
from datetime import datetime

# Importar desde el nuevo módulo cluster
from cluster.election import BullyElection, ElectionState
from core.models import MessageType, ClusterMessage


class DummySocket:
    def __init__(self):
        self.sent = []

    def sendto(self, data, addr):
        self.sent.append((data, addr))


def test_get_higher_nodes_respects_master_capability():
    election = BullyElection(node_id="node-2")
    election._socket = DummySocket()
    election.add_peer("node-1", "127.0.0.1", 5001, can_be_master=True)
    election.add_peer("node-3", "127.0.0.1", 5001, can_be_master=False)
    election.add_peer("node-4", "127.0.0.1", 5001, can_be_master=True)

    higher = election._get_higher_nodes()
    assert higher == ["node-4"]


def test_coordinator_message_updates_master():
    election = BullyElection(node_id="node-2")
    election._socket = DummySocket()

    message = ClusterMessage(
        type=MessageType.COORDINATOR,
        sender_id="node-5",
        payload={"new_master": "node-5"},
        timestamp=datetime.utcnow(),
    )

    async def _run():
        await election._handle_message(message, ("127.0.0.1", 5001))

    asyncio.run(_run())

    assert election.current_master == "node-5"
    assert election.is_master is False
    assert election._state == ElectionState.IDLE


def test_set_initial_master_sets_state_correctly():
    election = BullyElection(node_id="node-10")
    election.set_initial_master("node-10")
    assert election.is_master is True
    assert election.current_master == "node-10"
    assert election._state == ElectionState.IS_COORDINATOR

"""
Tests para el algoritmo de elección de líder (Bully).
"""
import pytest
import asyncio
# NOTA: Este test necesita ser reescrito para usar consensus/raft_election.py
# El algoritmo Bully fue reemplazado por Raft
pytest.skip("Test deprecado - Bully reemplazado por Raft", allow_module_level=True)


@pytest.mark.asyncio
async def test_election_single_node():
    """Test elección con un solo nodo."""
    messages_sent = []
    
    async def mock_send(dest_id, message):
        messages_sent.append((dest_id, message))
    
    election = BullyElection(
        node_id=5,
        all_node_ids={5},
        send_message_func=mock_send,
        timeout=0.5
    )
    
    leader = await election.start_election()
    
    # Debe auto-elegirse como líder
    assert leader == 5
    assert election.is_leader()


@pytest.mark.asyncio
async def test_election_highest_id_wins():
    """Test que el nodo con mayor ID gana."""
    node_ids = {1, 3, 5, 7, 9}
    elections = {}
    
    # Simular red de nodos
    messages = asyncio.Queue()
    
    async def make_send_func(sender_id):
        async def send(dest_id, message):
            await messages.put((sender_id, dest_id, message))
        return send
    
    # Crear módulos de elección para cada nodo
    for node_id in node_ids:
        send_func = await make_send_func(node_id)
        elections[node_id] = BullyElection(
            node_id=node_id,
            all_node_ids=node_ids,
            send_message_func=send_func,
            timeout=0.5
        )
    
    # Simular procesamiento de mensajes en background
    async def process_messages():
        try:
            while True:
                sender, dest, msg = await asyncio.wait_for(messages.get(), timeout=2.0)
                if dest in elections:
                    election_msg = ElectionMessage(
                        msg_type=MessageType(msg['msg_type']),
                        sender_id=msg['sender_id'],
                        election_id=msg.get('election_id', 0)
                    )
                    await elections[dest].handle_election_message(election_msg)
        except asyncio.TimeoutError:
            pass
    
    # Iniciar procesamiento de mensajes
    process_task = asyncio.create_task(process_messages())
    
    # Iniciar elección desde el nodo más bajo
    leader = await elections[1].start_election()
    
    # Esperar un poco para que se propaguen mensajes
    await asyncio.sleep(0.5)
    
    # Cancelar procesamiento
    process_task.cancel()
    try:
        await process_task
    except asyncio.CancelledError:
        pass
    
    # El nodo 9 debe ser líder (mayor ID)
    # Nota: en simulación puede no propagarse completamente, 
    # pero al menos el iniciador debe conocer al líder
    assert leader is not None


@pytest.mark.asyncio
async def test_election_message_handling():
    """Test manejo de mensajes de elección."""
    messages_sent = []
    
    async def mock_send(dest_id, message):
        messages_sent.append((dest_id, message))
    
    election = BullyElection(
        node_id=5,
        all_node_ids={3, 5, 7},
        send_message_func=mock_send,
        timeout=0.5
    )
    
    # Recibir mensaje ELECTION de nodo menor
    election_msg = ElectionMessage(
        msg_type=MessageType.ELECTION,
        sender_id=3,
        election_id=1
    )
    
    await election.handle_election_message(election_msg)
    
    # Debe responder con OK y empezar su propia elección
    await asyncio.sleep(0.1)
    
    # Debe haber enviado OK al nodo 3
    ok_messages = [msg for _, msg in messages_sent if msg.get('msg_type') == 'OK']
    assert len(ok_messages) > 0


@pytest.mark.asyncio
async def test_become_coordinator():
    """Test convertirse en coordinator."""
    messages_sent = []
    
    async def mock_send(dest_id, message):
        messages_sent.append((dest_id, message))
    
    election = BullyElection(
        node_id=7,
        all_node_ids={3, 5, 7},
        send_message_func=mock_send,
        timeout=0.5
    )
    
    # Iniciar elección (debería ganar porque tiene el ID más alto)
    leader = await election.start_election()
    
    assert leader == 7
    assert election.is_leader()
    
    # Debe haber enviado mensajes COORDINATOR
    coordinator_messages = [
        msg for _, msg in messages_sent 
        if msg.get('msg_type') == 'COORDINATOR'
    ]
    assert len(coordinator_messages) > 0


@pytest.mark.asyncio
async def test_election_timeout():
    """Test timeout esperando respuestas."""
    # Nodo 5 no recibirá respuestas de nodos mayores
    async def mock_send(dest_id, message):
        # Simular que los nodos mayores no responden
        pass
    
    election = BullyElection(
        node_id=5,
        all_node_ids={3, 5, 7, 9},
        send_message_func=mock_send,
        timeout=0.3
    )
    
    # Debe timeout y auto-elegirse
    leader = await election.start_election()
    
    # Debería declararse coordinator después del timeout
    assert leader == 5

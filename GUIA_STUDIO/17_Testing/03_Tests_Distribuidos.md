# Tests Distribuidos

## Objetivo
Validar comportamiento del cluster: Raft, rebalanceo, tolerancia a fallos, Gossip.

## Infraestructura
Usar docker-compose.test.yml para levantar mini-cluster:
```bash
docker compose -f docker/docker-compose.test.yml up -d
pytest tests/distributed -v
docker compose -f docker/docker-compose.test.yml down
```

## Ejemplos
```python
async def test_raft_leader_election():
    # Parar líder actual
    await stop_container("master-1")
    await asyncio.sleep(5)
    # Verificar nuevo líder
    status = await get_cluster_status()
    assert status["leader"] != "master-1"

async def test_rebalance_after_node_join():
    await add_node("slave-4")
    await trigger_rebalance()
    partitions = await get_partitions()
    assert "slave-4" in [p["node_id"] for p in partitions]
```

## Fixtures específicas
- `cluster`: levanta 3 nodos.
- `faulty_network`: simula particiones con `tc` o Toxiproxy.

## Ubicación
`tests/distributed/` y `backend/tests/test_adaptive_cluster.py`.
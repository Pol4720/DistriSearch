# Sincronización del UserDocumentRegistry

## Modelo
`UserDocumentRegistry` mantiene entradas `(user_id, document_id, node_id, vector_clock)` en SQLite local.

## Algoritmo Gossip
```python
async def sync_with_peer(peer_address):
    my_summary = get_vector_clock_summary()
    peer_summary = await send_summary_to_peer(peer_address, my_summary)
    diff = compute_diff(my_summary, peer_summary)
    entries_to_send = get_entries(diff.missing_on_peer)
    entries_received = await exchange_entries(peer_address, entries_to_send)
    merge_entries(entries_received)
```

## Frecuencia
- Intervalo configurable (default 10–30 s).
- Peer aleatorio por ronda para distribuir carga.

## Merge con vector clocks
- Si mi clock domina → conservo mi versión.
- Si peer domina → adopto versión del peer.
- Si concurrentes → last-write-wins por timestamp.

## Tombstones
- `is_deleted=True` marca borrados.
- Se propagan igual que entradas activas.
- Purgables tras TTL largo (ej. 7 días) para evitar resurrección.

## Beneficios
- Sin coordinador: cualquier nodo puede iniciar sync.
- Escala bien: O(log N) rondas para convergencia completa.
# Replicación de log (Raft)

## Ciclo del líder
1) Heartbeats cada 50 ms: `AppendEntries` vacío para afirmar liderazgo y reiniciar timers de seguidores (`_send_heartbeats`).
2) Al recibir un comando, el líder lo añade al log local con su término (`submit_command`) y dispara replicación inmediata.
3) Se esperan acks hasta alcanzar mayoría; sólo entonces el `commit_index` avanza y se aplica a la máquina de estados (`_maybe_advance_commit_index`).

## AppendEntries RPC
- Args: `term`, `leader_id`, `prev_log_index`, `prev_log_term`, `entries`, `leader_commit`.
- Reply: `term`, `success`, `match_index` (último índice replicado en el seguidor).
- Cada seguidor valida que `prev_log_index`/`prev_log_term` coincidan con su log; si no, responde `success=False` y el líder decrementa `next_index` para reintentar desde más atrás.

## Garantías de consistencia
- Un líder nunca confirma una entrada hasta que la mayoría la replicó y pertenece al término vigente (regla de seguridad Raft).
- Al aplicar entradas, los seguidores truncan y sobreescriben cualquier divergencia a partir de `prev_log_index`, garantizando logs idénticos tras convergencia.
- Los heartbeats transportan `leader_commit` para que seguidores apliquen entradas ya confirmadas.

## Flujo de aplicación
- Mayoría alcanzada → `commit_index` avanza → evento de apply → máquina de estados (SQLite) ejecuta en orden y actualiza `last_applied`.
- Si un comando no logra mayoría en 5 s (`replicate_entry` timeout), se reporta fallo pero puede reintentarse cuando el quórum vuelva.

## Recuperación ante fallos
- Líder cae: seguidores detectan falta de heartbeats y reinician elección con timeout aleatorio, evitando doble liderazgo.
- Seguidor rezagado: recibe `AppendEntries` con contexto de término/índice previos; si rechaza, el líder retrocede `next_index` hasta re-alinear.

## Compacción y snapshots
- Actualmente el log se mantiene completo; compacción/snapshots no están implementados, pero la máquina de estados persistente (SQLite) permite incorporarlos sin perder durabilidad.

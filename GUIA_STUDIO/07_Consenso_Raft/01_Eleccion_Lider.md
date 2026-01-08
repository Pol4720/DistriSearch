# Elección de líder (Raft)

## Flujo resumido
1) Cada nodo inicia como `Follower` y arranca un temporizador aleatorio 150–300 ms (`LeaderElection._get_election_timeout`).
2) Si no recibe `AppendEntries` (heartbeat) antes de expirar, pasa a `Candidate`, incrementa el término, vota por sí mismo y envía `RequestVote` a todos los peers (`start_election`).
3) Los peers otorgan el voto sólo si el término es al menos el actual y el log del candidato está tan actualizado como el suyo (`_is_log_up_to_date` compara `last_log_term` y `last_log_index`).
4) Con mayoría simple (⌈N/2⌉) el candidato gana y se convierte en `Leader` (`_win_election`), resetea el temporizador y arranca heartbeats.
5) Si cualquier RPC revela un término superior, el nodo hace step-down a `Follower` y limpia estado de líder (`update_term` + `become_follower`).

## RequestVote RPC
- Args: `term`, `candidate_id`, `last_log_index`, `last_log_term`.
- Reply: `term`, `vote_granted`.
- Se envía en paralelo a todos los nodos conocidos (excluyendo a sí mismo) y se toleran timeouts (se ignoran respuestas `None`).

## Prevención de split-brain
- La única vía a liderazgo es mayoría de votos sobre el mismo término; particiones sin mayoría no eligen líder.
- Comparación de logs evita que un nodo atrasado tome liderazgo aunque reciba votos previos.
- Heartbeats frecuentes (50 ms) reinician el temporizador de seguidores; si el líder cae, el timeout aleatorio reduce colisiones de elecciones simultáneas.

## Integración en DistriSearch
- `RaftNode.start()` inicia el temporizador de elección al boot; las llamadas `handle_append_entries` lo reinician cuando se escucha al líder.
- El líder es quien acepta escrituras de metadatos (usuarios, nodos, particiones) y dispara replicación del log; los demás redirigen o esperan.
- Configuración: habilitado por `RAFT_ENABLED=true` en despliegues Swarm; sin mayoría disponible el nodo queda como seguidor pasivo.

## Consideraciones operativas
- Clúster de un solo nodo: gana inmediatamente (se autoelige y pasa a líder).
- Rotación de liderazgo segura: al detectar término mayor en `RequestVote`/`AppendEntries`, el líder vigente se degrada a seguidor.
- Persistencia: `current_term` y `voted_for` se guardan en disco antes de responder, evitando votos duplicados tras reinicios.

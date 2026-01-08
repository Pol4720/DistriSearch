# Consenso Raft en DistriSearch

Raft coordina la vista de clúster (quién es el master) y la replicación de metadatos críticos (usuarios, nodos, particiones) para que los nodos actúen de forma coherente incluso con fallos o particiones de red.

## Qué resuelve
- Evita split-brain: sólo hay un líder con mandato vigente (término) y mayoría de votos.
- Propaga operaciones sensibles (alta/baja de nodos, usuarios, particiones) como un log replicado con commit por mayoría.
- Mantiene disponibilidad en modo AP: los nodos siguen sirviendo lectura/búsqueda aunque el líder cambie.

## Componentes clave
- `RaftNode`: orquesta estado, elección de líder, replicación y máquina de estados.
- `RaftState`: persistencia de `current_term` y `voted_for`, y estado volátil (commit_index, last_applied, match_index/next_index por seguidor).
- `LeaderElection`: temporizadores aleatorios 150–300 ms y RPC `RequestVote` para elegir líder.
- `LogReplicator`: `AppendEntries` como heartbeats (50 ms) y envío de entradas hasta confirmar por mayoría.
- `StateMachine/PersistentStateMachine`: aplica entradas comprometidas; en AP usa SQLite para guardar usuarios/nodos/particiones.

## Cuándo se activa
- Variable `RAFT_ENABLED=true` (ver deploy/manual-swarm/GUIA_DESPLIEGUE.md y scripts/06-deploy-slave.sh) habilita el stack Raft en los contenedores master/slave.
- Si no hay mayoría disponible, el nodo permanece seguidor y sólo sirve lectura local; al recuperar quórum retoma elecciones y sincroniza el log.

## Estados Raft (diagrama)
```
Follower --(timeout aleatorio)--> Candidate --(mayoría de votos)--> Leader
	^             |                                        |
	|             | (otro líder con término mayor)         |
	|             +--------------------> Follower <---------+
Leader --(heartbeat AppendEntries)--> Follower
```

En adelante: 01 detalla elección de líder, 02 la replicación de log y 03 el uso de SQLite como máquina de estados replicada.

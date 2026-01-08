# SQLite replicado con Raft

## Por qué SQLite
- Ligero y embebido: cada nodo persiste sus propios metadatos sin depender de un servicio externo.
- Funciona en particiones: escrituras entran sólo vía líder; si no hay quórum, el nodo mantiene lectura local y re-aplica al reunirse.
- Complementa a MongoDB (documentos y vectores) y Redis (cache) guardando credenciales, nodos y particiones críticas.

## Qué se replica
- Usuarios: altas/bajas/actualizaciones (`CREATE_USER`, `UPDATE_USER`, `DELETE_USER`).
- Nodos y membresía: `ADD_NODE`, `REMOVE_NODE`, `UPDATE_NODE` (direcciones, roles, estado).
- Particiones VP-Tree: asignaciones y movimientos (`ASSIGN_PARTITION`, `MOVE_PARTITION`, `REBALANCE`).
- Configuración y registro de documentos: `UPDATE_CONFIG`, `REGISTER_DOCUMENT`/`UNREGISTER_DOCUMENT` (se cruza con Gossip para convergencia eventual).

## Flujo de escritura
```
Cliente → Líder → append al log → AppendEntries a seguidores → mayoría confirma → commit_index avanza → PersistentStateMachine aplica en SQLite
```
- Cada entrada usa `Command` con `request_id` opcional para deduplicar; se persiste el resultado en `applied_requests`.
- Aplicación es ordenada y serializada con un lock interno; fallos durante apply reintentan al reiniciar porque el log es durable.

## Resiliencia y operación
- Reinicios: `current_term`/`voted_for` y el log están en disco; al boot se reanuda desde el último índice y se continua aplicando `last_applied+1`.
- Particiones de red: sin mayoría no hay nuevos commits, pero la base local sigue disponible para autenticación y lectura de metadatos ya aplicados.
- Integración con despliegue: `RAFT_ENABLED=true` en Swarm activa este modo; el repo SQLite se monta en el contenedor para no perder estado entre recreaciones.

## Beneficios para autenticación y control
- Inicio de sesión y permisos no dependen de MongoDB ni de conectividad total; mientras el líder exista con quórum, las credenciales se replican.
- El registro de nodos y particiones consistente evita que dos masters acepten cambios contradictorios; el líder único serialize las mutaciones.

# Consistencia Eventual

## Definición
Si no hay nuevas escrituras, eventualmente todas las réplicas convergen al mismo estado.

## Trade-off CAP en DistriSearch
DistriSearch elige **AP** (Available + Partition-tolerant):
- Durante particiones, cada nodo sigue sirviendo lecturas/escrituras locales.
- Tras reunirse, Gossip sincroniza diferencias.

## Cuándo es aceptable
- Listado de documentos de un usuario: tolera ver un doc nuevo con pequeño retraso.
- Estadísticas de cluster: no crítico que sean instantáneas.

## Cuándo NO es aceptable
- Autenticación: por eso usuarios van en SQLite+Raft (consistencia fuerte).
- Asignación de particiones: también Raft.

## Resolución de conflictos
- Vector clocks: detectan concurrencia.
- Last-write-wins si clocks son incomparables.
- Soft-deletes (tombstones) para evitar resurrección de datos borrados.
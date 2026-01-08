# Disponibilidad y Tolerancia a Particiones

## Por qué AP para búsqueda
- Los usuarios esperan resultados aunque parte del cluster esté caído.
- Un sistema CP bloquearía peticiones hasta recuperar quorum.
- Búsqueda semejante tolera resultados ligeramente desactualizados.

## Operación durante partición
```
[Partición de red]
Grupo A (master + slave1)   |   Grupo B (slave2, slave3)
- Raft sin quorum → no escribe SQLite
- Lecturas locales OK
- Búsqueda en docs locales OK
```
Cada grupo sigue sirviendo sus documentos. Al reunirse, Gossip sincroniza y Raft elige nuevo líder si es necesario.

## Modo degradado
- Autenticación: funciona si el nodo tiene usuarios en SQLite local (datos replicados previamente).
- Escrituras de usuarios/nodos: bloqueadas sin mayoría Raft.
- Subida de documentos: se almacena localmente; replicación se completa al reunirse.

## Comparación con sistemas CP
| Sistema | Comportamiento en partición |
|---------|-----------------------------|
| CP (ej. Spanner) | Rechaza escrituras sin quorum |
| AP (DistriSearch) | Acepta localmente, sincroniza después |
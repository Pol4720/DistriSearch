# SQLite para Usuarios y Metadatos

## Por qué SQLite
- Embebido: no requiere servidor externo.
- Funciona durante particiones: cada nodo tiene copia local.
- Replicado vía Raft para consistencia fuerte entre mayoría.

## Qué se almacena
- Usuarios: credenciales, roles, permisos.
- Nodos: membrísía del cluster, direcciones, estados.
- Particiones: asignaciones VP-Tree.
- Configuración: parámetros del sistema.
- applied_requests: deduplicación de comandos Raft.

## Flujo de escritura
```
Cliente → Líder Raft → append log → replicar a seguidores → commit → aplicar en SQLite
```

## Repositorios
- `SQLiteUserRepository`: CRUD de usuarios.
- `SQLiteNodeRepository`: CRUD de nodos.
- `SQLitePartitionRepository`: CRUD de particiones.

## Beneficios para AP
- Autenticación local: el nodo puede validar JWT con su SQLite aunque esté particionado.
- Metadatos de cluster disponibles para operaciones de sólo lectura.
# Servicios y réplicas

## Modos de despliegue
| Modo | Comportamiento |
|------|----------------|
| `replicated` | N tareas fijas distribuidas por el scheduler |
| `global` | Exactamente 1 tarea por nodo que cumpla constraints |

En DistriSearch:
- `slave`, `coredns`, `load-balancer`, `master`, `mongodb` usan **global** para escalar automáticamente al agregar nodos.
- `redis` y `dns-sync` usan **replicated: 1** (singleton).

## Endpoint modes
| Modo | Resolución DNS |
|------|----------------|
| `vip` (default) | Nombre → IP virtual única; Swarm balancea internamente |
| `dnsrr` | Nombre → lista de IPs de tareas; cliente elige |

- `slave` usa `vip` para balanceo transparente.
- `master` y `mongodb` usan `dnsrr` para control fino de conexión (Raft, replica set).

## Placement constraints
```yaml
placement:
  constraints:
    - node.role == manager
```
Restringe el servicio a nodos manager (master, load-balancer, mongodb, redis).

## Recursos
```yaml
resources:
  limits:
    cpus: '2.0'
    memory: 2G
  reservations:
    cpus: '0.5'
    memory: 512M
```
- **limits**: máximo que puede consumir.
- **reservations**: mínimo garantizado; el scheduler sólo coloca la tarea si el nodo tiene esos recursos libres.
# DNS interno de Docker Swarm

## Cómo funciona
Cada contenedor en una red overlay tiene `127.0.0.11` como resolver; las consultas se envían al daemon de Docker que mantiene registros de todos los servicios.

## Tipos de resolución
| Consulta | Resultado |
|----------|----------|
| `master` | VIP única (si `endpoint_mode: vip`) balanceada internamente |
| `tasks.master` | Lista de IPs de todas las tareas corriendo |
| `master.1.abc123` | IP de contenedor específico |

## endpoint_mode
- **vip** (default): un registro A con IP virtual; Swarm balancea internamente.
- **dnsrr**: múltiples registros A; el cliente elige (usado en `master`, `mongodb` para Raft/replica set).

## Ejemplo de flujo
```
Slave → resolver 127.0.0.11 → "master" → 10.0.10.5
      ← respuesta IP        ← Docker DNS
Slave → TCP 10.0.10.5:8001 → Master container
```

## Limitaciones
- Dependiente del health del Swarm manager.
- Puede saturarse bajo alto volumen de queries.
- Por eso DistriSearch habilita un respaldo CoreDNS.
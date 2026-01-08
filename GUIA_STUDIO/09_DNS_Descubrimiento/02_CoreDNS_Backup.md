# CoreDNS como DNS de respaldo

Cuando Docker DNS falla (saturación, partición, bug), CoreDNS responde con zonas pre-sincronizadas.

## Archivo Corefile
```
distrisearch.local:53 {
    log
    errors
    file /etc/coredns/zones/distrisearch.local.zone
    loadbalance round_robin
    cache 30
    forward . 127.0.0.11   ; reenvía a Docker DNS si no está en zona
}

services.distrisearch.local:53 { ... }

. {
    forward . 127.0.0.11 8.8.8.8 8.8.4.4
    cache 60
}
```

## Plugins clave
| Plugin | Función |
|--------|--------|
| file | Carga zona desde archivo |
| loadbalance | Rotación round-robin de registros A |
| cache | Reduce latencia y carga |
| forward | Reenvía consultas no resueltas |
| rewrite | Mapea `master.distrisearch.local` → `master` para compatibilidad |

## dns-sync daemon
`sync_dns_zone.py` corre cada `SYNC_INTERVAL` (30 s):
1. Conecta a Docker API.
2. Lista servicios y extrae IPs de tareas corriendo.
3. Genera zona con registros A dinámicos.
4. Escribe `/zones/distrisearch.local.zone`; CoreDNS recarga automáticamente.

## Despliegue
- `coredns` modo global: una instancia por nodo para resolución local rápida.
- `dns-sync` modo replicated (1): singleton en manager con acceso a Docker socket.
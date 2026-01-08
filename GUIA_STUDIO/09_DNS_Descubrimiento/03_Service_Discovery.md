# Service Discovery y cadena de fallback

## Cadena de resolución
```
1. Docker DNS 127.0.0.11   → éxito → usar IP
        ↓ fallo
2. CoreDNS coredns:53      → éxito → usar IP
        ↓ fallo
3. Caché local / /etc/hosts → éxito → usar IP
        ↓ fallo
4. Error de resolución
```

## Variables de entorno
| Variable | Valor ejemplo | Descripción |
|----------|---------------|-------------|
| DNS_FALLBACK_ENABLED | true | Activa cadena |
| COREDNS_HOST | coredns | Host del servidor backup |
| MASTER_SERVICE | master | Nombre de servicio master |
| MONGODB_URI | mongodb://mongodb:27017 | Resuelto por DNS |

## Integración en la aplicación
- Al iniciar, el backend intenta resolver `master`; si falla, usa CoreDNS.
- Conexiones a MongoDB y Redis usan el mismo flujo.
- El healthcheck (`/health`) valida conectividad DNS; si falla, Swarm reinicia el contenedor.

## Beneficios
- Resiliencia ante fallos del daemon Docker.
- Permite operar en modo degradado durante particiones de red.
- Caché reduce latencia de resolución en operaciones frecuentes.
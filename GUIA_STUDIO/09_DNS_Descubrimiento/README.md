# DNS y Descubrimiento de Servicios

En un sistema distribuido los contenedores necesitan localizarse dinámicamente. DistriSearch combina el DNS nativo de Docker Swarm con un respaldo CoreDNS para garantizar alta disponibilidad del descubrimiento.

## Estrategia de resolución
1. **Docker DNS (127.0.0.11)** – primera opción; automático en Swarm.
2. **CoreDNS backup** – si Docker DNS falla, se consulta `coredns:53`.
3. **Caché local / /etc/hosts** – último recurso estático.

## Componentes
| Componente | Rol |
|------------|-----|
| Docker DNS | Resuelve nombres de servicio a VIP o lista de tareas |
| CoreDNS | Respaldo configurable con zonas `distrisearch.local` y `services.distrisearch.local` |
| dns-sync | Daemon que sincroniza IPs de servicios Swarm a zona CoreDNS cada 30 s |

## Variables de entorno relevantes
- `DNS_FALLBACK_ENABLED=true` – activa cadena de fallback.
- `COREDNS_HOST=coredns` – dirección del servidor de respaldo.

En los siguientes archivos se profundiza cada capa.
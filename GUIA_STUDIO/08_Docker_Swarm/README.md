# Docker Swarm en DistriSearch

Docker Swarm orquesta el despliegue de DistriSearch: gestiona contenedores distribuidos, redes overlay, descubrimiento DNS, balanceo de carga y actualizaciones sin corte de servicio.

## Por qué Swarm y no Kubernetes
- Simplicidad: configuración declarativa en docker-compose.swarm.yml; mismo conocimiento de Docker Compose.
- DNS integrado: resolución automática de nombres de servicio (p.ej. "master", "mongodb").
- Routing mesh nativo: cualquier nodo puede recibir tráfico y reenviarlo al servicio correcto.
- Self-healing y rolling updates sin dependencias externas.
- Menor overhead operativo para clusters medianos.

## Servicios principales
| Servicio | Modo | Constraint | Descripción |
|----------|------|------------|-------------|
| load-balancer | global | manager | Nginx en cada manager |
| master | global | manager | Nodo Raft maestro |
| slave | global | cualquiera | Backend + frontend |
| mongodb | global | manager | Replica set local |
| redis | replicated (1) | manager | Cache centralizado |
| coredns | global | cualquiera | DNS de respaldo |
| dns-sync | replicated (1) | manager | Sincroniza zona DNS |

## Redes
- `distrisearch-network` (overlay 10.0.10.0/24): comunicación interna entre servicios.
- `ingress-network` (overlay): routing mesh para tráfico externo.

En los siguientes archivos se profundiza cada concepto.